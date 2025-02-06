import * as path from "node:path";
import { PythonFunction } from "@aws-cdk/aws-lambda-python-alpha";
import { bedrock } from "@cdklabs/generative-ai-cdk-constructs";
import {
  aws_dynamodb,
  aws_s3,
  aws_s3_deployment,
  CfnOutput,
  Duration,
  RemovalPolicy,
  Stack,
  StackProps,
} from "aws-cdk-lib";
import { Architecture, Runtime, RuntimeFamily } from "aws-cdk-lib/aws-lambda";

import { LambdaPowertoolsLayer } from "cdk-aws-lambda-powertools-layer";
import { Construct } from "constructs";

interface BackendStackProps extends StackProps {}

export class BackendStack extends Stack {
  public readonly agent: bedrock.Agent;
  public readonly agentAlias: bedrock.AgentAlias;
  constructor(scope: Construct, id: string, props: BackendStackProps = {}) {
    super(scope, id, props);

    //create a dynamodb table to store tickets
    const ticketsTable = new aws_dynamodb.Table(this, "ticketsTable", {
      partitionKey: {
        name: "user_id",
        type: aws_dynamodb.AttributeType.STRING,
      },
      sortKey: { name: "id", type: aws_dynamodb.AttributeType.STRING },
      billingMode: aws_dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: aws_dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecovery: true,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    //create a dynamodb table to store users
    const usersTable = new aws_dynamodb.Table(this, "usersTable", {
      partitionKey: { name: "id", type: aws_dynamodb.AttributeType.STRING },

      billingMode: aws_dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: aws_dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecovery: true,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    const powerToolsLayer = new LambdaPowertoolsLayer(
      this,
      "lambda-powertools-layer",
      {
        includeExtras: true,
        compatibleArchitectures: [Architecture.ARM_64],
        runtimeFamily: RuntimeFamily.PYTHON,
      },
    );

    const usersFunction = new PythonFunction(this, "usersFunction", {
      runtime: Runtime.PYTHON_3_12,
      entry: path.join(__dirname, "functions", "users"),
      layers: [powerToolsLayer],
      environment: {
        TABLE_NAME: usersTable.tableName,
      },
      architecture: Architecture.ARM_64,
    });

    const ticketsFunction = new PythonFunction(this, "ticketsFunction", {
      runtime: Runtime.PYTHON_3_12,
      entry: path.join(__dirname, "functions", "tickets"),
      layers: [powerToolsLayer],
      environment: {
        TABLE_NAME: ticketsTable.tableName,
      },
      architecture: Architecture.ARM_64,
    });

    ticketsTable.grantReadWriteData(ticketsFunction);
    usersTable.grantReadWriteData(usersFunction);

    const kb = new bedrock.KnowledgeBase(this, "knowledgeBase", {
      embeddingsModel: bedrock.BedrockFoundationModel.TITAN_EMBED_TEXT_V2_1024,
      instruction:
        "Use this knowledge base to answer questions from users and find troubleshooting procedures. It contains common questions and the full text of troubleshooting and operating procedures.",
    });

    const kbBucket = new aws_s3.Bucket(this, "kbBucket", {
      removalPolicy: RemovalPolicy.DESTROY,
      enforceSSL: true,
    });

    new aws_s3_deployment.BucketDeployment(this, "deployKbContent", {
      sources: [
        aws_s3_deployment.Source.asset(path.join(__dirname, "kbContent")),
      ],
      destinationBucket: kbBucket,
      prune: false,
    });

    new bedrock.S3DataSource(this, "kbDatasource", {
      bucket: kbBucket,
      knowledgeBase: kb,
      dataSourceName: "kbDatasource",
    });

    const instruction = `
        You are a helpdesk assistant for an internet provider. You will be provided with a user prompt, and need to assist them in resolving the issue or creating a ticket.
        You are talking to the user directly, and address them as such in a friendly and informal manner. Show empathy for the user's problem and try to deesclalate the situation if there is tension. Address the user in the first person as if you are having a direct conversation with them using "you" and "yours". Only use their name when greeting them.
        If information is required but not known, attempt to look it up first and then ask the user.
        Before asking any questions, greet them, introduce yourself, provide a brief description of the process you will follow, then validate their problem statement.
        Try and discover their problem statement by asking them a series of questions
        Ask each question one by one.
        Directly ask any question without explaining what you are doing.
        Do not ask multiple questions in the same response, and provide responses and questions separately.
        Do not provide your reasoning process or reveal internal information.
        If parameters for an action group are not known, explicitly ask for them, do not make anything up. 
        When performing any actions, always ask for a user id. 
        After gathering all the required information and asking all questions, use your knowledge base to attempt to determine a root cause and provide the user with a step by step procedure to attempt to resolve the issue. Ask the user if this was successful. If not succesful after 3 attempts, determine a root cause to the best of your abilities and create a ticket. Provide the ticket id to the user and ask if there is anything else they need help with. If not, thank them and end the session."
        `;

    // const inferenceProfile = bedrock.CrossRegionInferenceProfile.fromConfig({
    //   geoRegion: bedrock.CrossRegionInferenceProfileRegion.US,
    //   model: bedrock.BedrockFoundationModel.AMAZON_NOVA_PRO_V1,
    // });
    const cris = bedrock.CrossRegionInferenceProfile.fromConfig({
      geoRegion: bedrock.CrossRegionInferenceProfileRegion.US,
      model: bedrock.BedrockFoundationModel.ANTHROPIC_CLAUDE_3_5_HAIKU_V1_0,
    });

    const userActionGroup = new bedrock.AgentActionGroup(
      this,
      "userActionGroup",
      {
        actionGroupName: "user-actions",
        description:
          "Use these functions to get information about users, create users, or update users.",
        apiSchema: bedrock.ApiSchema.fromAsset(
          path.join(__dirname, "functions", "users", "schema.json"),
        ),
        actionGroupExecutor: {
          lambda: usersFunction,
        },
        actionGroupState: "ENABLED",
        skipResourceInUseCheckOnDelete: true,
      },
    );

    const ticketActionGroup = new bedrock.AgentActionGroup(
      this,
      "ticketActionGroup",
      {
        actionGroupName: "ticket-actions",
        description:
          "Use these functions to get information about tickets, create tickets, or update tickets.",
        apiSchema: bedrock.ApiSchema.fromAsset(
          path.join(__dirname, "functions", "tickets", "schema.json"),
        ),
        actionGroupExecutor: {
          lambda: ticketsFunction,
        },
        actionGroupState: "ENABLED",
        skipResourceInUseCheckOnDelete: true,
      },
    );

    const agent = new bedrock.Agent(this, "helpdeskChatAgent", {
      knowledgeBases: [kb],
      instruction: instruction,
      foundationModel: cris,
      //foundationModel: bedrock.BedrockFoundationModel.ANTHROPIC_CLAUDE_3_5_HAIKU_V1_0,
      idleSessionTTL: Duration.minutes(10),
      shouldPrepareAgent: true,
      //aliasName: "helpdeskAgent",
      //existingRole: bedrockAgentRole,
    });

    const agentAlias = new bedrock.AgentAlias(this, "helpdeskChatAgentAlias", {
      aliasName: "helpdeskAgent",
      agentId: agent.agentId,
      description: "v2 helpdesk agent",
      //agentVersion: "2",
    });
    this.agentAlias = agentAlias;
    this.agent = agent;

    /*    new bedrock.AgentAlias(this, "helpdeskChatAgentAlias", {
      aliasName: "helpdeskAgent",
      agentId: agent.agentId,
      description: "v2 helpdesk agent",
    });*/

    agent.addActionGroups([userActionGroup, ticketActionGroup]);
    new CfnOutput(this, "ticketFunctionArn", {
      value: ticketsFunction.functionArn,
      description: "tickets Function Arn",
    });

    new CfnOutput(this, "userFunctionArn", {
      value: usersFunction.functionArn,
      description: "users Function Arn",
    });
    new CfnOutput(this, "kbArn", {
      value: kb.knowledgeBaseArn,
      description: "kb Arn",
    });
    new CfnOutput(this, "usersTableArn", {
      value: usersTable.tableArn,
      description: "users Table Arn",
    });
    new CfnOutput(this, "ticketTableArn", {
      value: ticketsTable.tableArn,
      description: "tickets Table Arn",
    });
  }
}
