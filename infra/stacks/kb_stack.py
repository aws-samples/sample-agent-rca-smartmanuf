"""CDK Stack: Bedrock Knowledge Bases (Hybrid + GraphRAG) using generative-ai-cdk-constructs."""

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    RemovalPolicy,
    CfnOutput,
    aws_iam as iam,
    aws_s3 as s3,
)
from constructs import Construct
from cdklabs.generative_ai_cdk_constructs import (
    bedrock,
    neptune,
)


class RcaKbStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        embedding_model = bedrock.BedrockFoundationModel.TITAN_EMBED_TEXT_V2_1024

        # S3 bucket for KB data source (shared by both KBs)
        self.data_bucket = s3.Bucket(
            self,
            "KbDataBucket",
            bucket_name=f"rca-kb-data-{self.account}-{self.region}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            enforce_ssl=True,
        )

        # --- Hybrid KB (OpenSearch Serverless) ---
        self.hybrid_kb = bedrock.VectorKnowledgeBase(
            self,
            "HybridKb",
            embeddings_model=embedding_model,
            description="Manufacturing RCA hybrid search (keyword + semantic)",
            instruction="Use this knowledge base for detailed manufacturing data retrieval "
            "including batch records, deviation reports, equipment logs, and procedures.",
        )

        hybrid_ds = self.hybrid_kb.add_s3_data_source(
            bucket=self.data_bucket,
            data_source_name="rca-manufacturing-data",
            chunking_strategy=bedrock.ChunkingStrategy.SEMANTIC,
        )

        # --- GraphRAG KB (Neptune Analytics) ---
        graph = neptune.NeptuneGraph(
            self,
            "RcaGraph",
            vector_search_dimension=embedding_model.vector_dimensions,
        )
        graph.apply_removal_policy(RemovalPolicy.DESTROY)

        self.graphrag_kb = bedrock.GraphKnowledgeBase(
            self,
            "GraphRagKb",
            embedding_model=embedding_model,
            graph=graph,
            description="Manufacturing RCA graph knowledge base (entity relationships)",
            instruction="Use this knowledge base to discover relationships between "
            "equipment, materials, processes, and quality events across documents.",
        )

        enrichment_model = bedrock.CrossRegionInferenceProfile.from_config(
            model=bedrock.BedrockFoundationModel(
                "anthropic.claude-haiku-4-5-20251001-v1:0",
                supports_cross_region=True,
            ),
            geo_region=bedrock.CrossRegionInferenceProfileRegion.EU,
        )

        self.graphrag_kb.role.add_to_principal_policy(
            iam.PolicyStatement(
                actions=["bedrock:GetInferenceProfile", "bedrock:ListInferenceProfiles"],
                resources=["*"],
            )
        )
        self.graphrag_kb.role.add_to_principal_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=[
                    f"arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0",
                    f"arn:aws:bedrock:eu-central-1:{self.account}:inference-profile/eu.anthropic.claude-haiku-4-5-20251001-v1:0",
                ],
            )
        )

        graphrag_ds = self.graphrag_kb.add_s3_data_source(
            bucket=self.data_bucket,
            data_source_name="rca-manufacturing-graphrag",
            context_enrichment=bedrock.ContextEnrichment.foundation_model(
                enrichment_model=enrichment_model,
            ),
        )

        # --- Outputs ---
        CfnOutput(self, "DataBucketName", value=self.data_bucket.bucket_name)
        CfnOutput(self, "HybridKbId", value=self.hybrid_kb.knowledge_base_id)
        CfnOutput(self, "HybridDataSourceId", value=hybrid_ds.data_source_id)
        CfnOutput(self, "GraphRagKbId", value=self.graphrag_kb.knowledge_base_id)
        CfnOutput(self, "GraphRagDataSourceId", value=graphrag_ds.data_source_id)
        CfnOutput(self, "KbRoleArn", value=self.hybrid_kb.role.role_arn)
