import { App, Aspects } from "aws-cdk-lib";
import { AwsSolutionsChecks, NagSuppressions } from "cdk-nag";
import { BackendStack } from "./stacks/backend/main";
import { FrontendStack } from "./stacks/frontend/main";
// for development, use account/region from cdk cli
const prodEnv = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: "us-east-1",
};

const app = new App();

const backend = new BackendStack(app, "helpdesk-backend", { env: prodEnv });

const frontend = new FrontendStack(app, "helpdesk-ui", {
  env: prodEnv,
  agentId: backend.agentAlias.agentId,
  agentAliasId: backend.agentAlias.aliasId,
});

const suppressions = [
  {
    id: "AwsSolutions-IAM4",
    reason: "AWS Managed policies are fine",
  },
  {
    id: "AwsSolutions-IAM5",
    reason: "Wildcards are fine as we access multiple resources",
  },
  {
    id: "AwsSolutions-L1",
    reason: "powertools restricts us to 3.12",
  },
  {
    id: "AwsSolutions-S1",
    reason: "bucket is used for KB",
  },
  {
    id: "AwsSolutions-ELB2",
    reason: "not required for POC",
  },
  {
    id: "AwsSolutions-ECS2",
    reason: "these are public environment data",
  },
  {
    id: "AwsSolutions-ECS4",
    reason: "not required",
  },
  {
    id: "AwsSolutions-VPC7",
    reason: "not required",
  },
  {
    id: "AwsSolutions-CFR3",
    reason: "not required",
  },
  {
    id: "AwsSolutions-CFR4",
    reason: "we are using the default cloudfront certificate",
  },
  {
    id: "AwsSolutions-CFR5",
    reason: "backend traffic is unencrypted as this is a POC",
  },
];

NagSuppressions.addStackSuppressions(frontend, suppressions);
NagSuppressions.addStackSuppressions(backend, suppressions);

Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));
app.synth();
