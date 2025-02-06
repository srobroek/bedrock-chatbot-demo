import * as path from "node:path";
import {
  aws_cloudfront,
  aws_cloudfront_origins,
  aws_ec2,
  aws_ecr_assets,
  aws_ecs,
  aws_ecs_patterns,
  aws_iam,
  CfnOutput,
  Stack,
  StackProps,
} from "aws-cdk-lib";

import { OriginSslPolicy } from "aws-cdk-lib/aws-cloudfront";
import { Construct } from "constructs";

interface FrontendStackProps extends StackProps {
  agentId: string;
  agentAliasId: string;
}

export class FrontendStack extends Stack {
  constructor(scope: Construct, id: string, props: FrontendStackProps) {
    super(scope, id, props);

    const dockerImage = new aws_ecr_assets.DockerImageAsset(
      this,
      "streamlit-app",
      {
        directory: path.join(__dirname, "streamlit-app"),
        file: "Dockerfile",
        platform: aws_ecr_assets.Platform.LINUX_ARM64,
      },
    );

    const image = aws_ecs.ContainerImage.fromDockerImageAsset(dockerImage);

    const service = new aws_ecs_patterns.ApplicationLoadBalancedFargateService(
      this,
      "streamlit-frontend-svc",
      {
        taskImageOptions: {
          image: image,
          containerPort: 8501,
          environment: {
            BEDROCK_AGENT_ID: `${props.agentId}`,
            BEDROCK_AGENT_ALIAS_ID: `${props.agentAliasId}`,
            BEDROCK_AGENT_REGION: Stack.of(this).region,
          },
          taskRole: new aws_iam.Role(this, "ECSTaskRole", {
            assumedBy: new aws_iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            inlinePolicies: {
              bedrock: new aws_iam.PolicyDocument({
                statements: [
                  new aws_iam.PolicyStatement({
                    actions: ["bedrock:InvokeAgent", "bedrock:InvokeModel"],
                    resources: [
                      `arn:aws:bedrock:${Stack.of(this).region}:${Stack.of(this).account}:agent/*`,
                      `arn:aws:bedrock:${Stack.of(this).region}:${Stack.of(this).account}:agent-alias/*`,
                      `arn:aws:bedrock:${Stack.of(this).region}::foundation-model/*`,
                    ],
                    effect: aws_iam.Effect.ALLOW,
                  }),
                ],
              }),
            },
          }),
        },
        runtimePlatform: {
          cpuArchitecture: aws_ecs.CpuArchitecture.ARM64,
          operatingSystemFamily: aws_ecs.OperatingSystemFamily.LINUX,
        },
        publicLoadBalancer: true,
        assignPublicIp: true,
        memoryLimitMiB: 2048,
        cpu: 512,
        securityGroups: [],
        openListener: false,
      },
    );

    service.targetGroup.configureHealthCheck({
      path: "/",
      port: "8501",
    });

    service.loadBalancer.connections.allowTo(
      service.service,
      aws_ec2.Port.tcp(8501),
    );

    //service.loadBalancer.connections.allowDefaultPortFromAnyIpv4()
    const cloudfrontPrefixList = aws_ec2.PrefixList.fromPrefixListId(
      this,
      "cloudfrontprefix",
      "pl-3b927c52",
    );

    const alb_sg_http = new aws_ec2.SecurityGroup(this, "alb-sg-http", {
      vpc: service.cluster.vpc,
      allowAllOutbound: false,
    });

    const alb_sg_https = new aws_ec2.SecurityGroup(this, "alb-sg-https", {
      vpc: service.cluster.vpc,
      allowAllOutbound: false,
    });

    alb_sg_http.addIngressRule(
      aws_ec2.Peer.prefixList(cloudfrontPrefixList.prefixListId),
      aws_ec2.Port.HTTP,
    );
    alb_sg_https.addIngressRule(
      aws_ec2.Peer.prefixList(cloudfrontPrefixList.prefixListId),
      aws_ec2.Port.HTTPS,
    );

    service.loadBalancer.addSecurityGroup(alb_sg_http);
    service.loadBalancer.addSecurityGroup(alb_sg_https);




    const distribution = new aws_cloudfront.Distribution(this, "cloudfront", {
      minimumProtocolVersion:
        aws_cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
      defaultBehavior: {
        origin: new aws_cloudfront_origins.LoadBalancerV2Origin(
          service.loadBalancer,
          {
            protocolPolicy: aws_cloudfront.OriginProtocolPolicy.HTTP_ONLY,
            originSslProtocols: [OriginSslPolicy.TLS_V1_2],
          },
        ),

        cachePolicy: aws_cloudfront.CachePolicy.CACHING_DISABLED,
        allowedMethods: aws_cloudfront.AllowedMethods.ALLOW_ALL,
        viewerProtocolPolicy:
          aws_cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        originRequestPolicy: aws_cloudfront.OriginRequestPolicy.ALL_VIEWER,
      },


      enabled: true,
      defaultRootObject: "",

      priceClass: aws_cloudfront.PriceClass.PRICE_CLASS_100,

    });

    // Add these after creating your distribution
    new CfnOutput(this, "DistributionId", {
      value: distribution.distributionId,
      description: "CloudFront Distribution ID",
    });

    new CfnOutput(this, "DistributionDomain", {
      value: distribution.distributionDomainName,
      description: "CloudFront Distribution Domain Name",
    });

    new CfnOutput(this, "LoadBalancerDNS", {
      value: service.loadBalancer.loadBalancerDnsName,
      description: "ALB Domain Name",
    });

    new CfnOutput(this, "DistributionURL", {
      value: `https://${distribution.distributionDomainName}`,
      description: "CloudFront Distribution URL",
    });

    // If you want to export these values for use in other stacks
    new CfnOutput(this, "DistributionIdExport", {
      value: distribution.distributionId,
      description: "CloudFront Distribution ID",
      exportName: `${this.stackName}-distribution-id`,
    });

    new CfnOutput(this, "DistributionDomainExport", {
      value: distribution.distributionDomainName,
      description: "CloudFront Domain Name",
      exportName: `${this.stackName}-distribution-domain`,
    });
  }
}
