# AWS Bedrock Setup Guide

This guide will help you configure AWS Bedrock for use with your Theory2Manim application.

## Prerequisites

1. **AWS Account**: You need an active AWS account
2. **AWS CLI** (optional): For easier credential management
3. **AWS Bedrock Access**: Your AWS account must have access to AWS Bedrock service

## Step 1: Enable AWS Bedrock Models

1. Log into your AWS Console
2. Navigate to AWS Bedrock service
3. Go to "Model access" in the left sidebar
4. Request access to the models you want to use:
   - **Anthropic Claude Models** (Recommended)
     - Claude 3.5 Sonnet
     - Claude 3.5 Haiku
     - Claude 3.7 Sonnet (with reasoning)
     - Claude 4 Sonnet
   - **Amazon Nova Models**
     - Nova Pro
     - Nova Lite
     - Nova Micro
   - **Meta Llama Models**
     - Llama 3.1 405B
     - Llama 3.1 70B
   - **Other Models**
     - Cohere Command R+
     - Mistral Large

## Step 2: Get AWS Credentials

### Option A: AWS CLI (Recommended)
```bash
# Install AWS CLI
pip install awscli

# Configure AWS credentials
aws configure
```

### Option B: Manual Setup
1. In AWS Console, go to IAM → Users → Your User → Security credentials
2. Create new Access Key
3. Note down:
   - Access Key ID
   - Secret Access Key

## Step 3: Configure Environment Variables

Create or update your `.env` file with:

```bash
# AWS Bedrock Configuration
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key
AWS_REGION_NAME=us-west-2  # or your preferred region

# Optional: AWS Session Token (for temporary credentials)
# AWS_SESSION_TOKEN=your_session_token
```

## Step 4: Available Bedrock Models

The following models are now available in your application:

### Anthropic Claude Models
- `bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0` - Excellent reasoning
- `bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0` - Latest Claude 3.5
- `bedrock/anthropic.claude-3-5-haiku-20241022-v1:0` - Fast responses
- `bedrock/us.anthropic.claude-3-7-sonnet-20250219-v1:0` - Advanced reasoning with thinking
- `bedrock/anthropic.claude-sonnet-4-20250115-v1:0` - Latest Claude 4

### Amazon Nova Models
- `bedrock/us.amazon.nova-pro-v1:0` - Amazon's flagship model
- `bedrock/us.amazon.nova-lite-v1:0` - Fast and efficient
- `bedrock/us.amazon.nova-micro-v1:0` - Ultra-fast responses

### Meta Llama Models
- `bedrock/meta.llama3-1-405b-instruct-v1:0` - Meta's largest model
- `bedrock/meta.llama3-1-70b-instruct-v1:0` - Balanced performance

### Other Models
- `bedrock/cohere.command-r-plus-v1:0` - Advanced Cohere model
- `bedrock/mistral.mistral-large-2402-v1:0` - Powerful Mistral model

## Step 5: Test Your Configuration

You can test your Bedrock configuration with this Python script:

```python
from mllm_tools.bedrock import BedrockWrapper

# Test basic chat
wrapper = BedrockWrapper(
    model_name="bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0"
)

# Simple test
response = wrapper.chat([
    {"role": "user", "content": "Hello! Can you explain quantum computing in simple terms?"}
])
print(response)
```

## Step 6: Using in Theory2Manim

Once configured, you can use Bedrock models in your Theory2Manim application:

1. **In the UI**: Select "AWS Bedrock" as your provider and choose a model
2. **Command Line**: Use the `--model` parameter with a Bedrock model name
3. **Configuration**: Set the default model in your config files

Example command:
```bash
python generate_video.py --topic "Quantum Computing" --model "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0"
```

## Troubleshooting

### Common Issues

1. **Access Denied Error**
   - Ensure your AWS account has Bedrock access
   - Check that you've requested access to the specific model
   - Verify your AWS credentials are correct

2. **Region Issues**
   - Some models are only available in specific regions
   - Try changing `AWS_REGION_NAME` to `us-west-2` or `us-east-1`

3. **Quota Limits**
   - New accounts may have lower usage quotas
   - Request quota increases in the AWS Console if needed

### Getting Help

- Check AWS Bedrock documentation: https://docs.aws.amazon.com/bedrock/
- Review your AWS CloudTrail logs for detailed error information
- Ensure your IAM user has `bedrock:*` permissions

## Cost Optimization

- Start with smaller models like Claude 3.5 Haiku for testing
- Use the `print_cost=True` parameter to monitor usage
- Consider using Amazon Nova models for cost-effective solutions

## Security Best Practices

1. **Never commit credentials to version control**
2. **Use IAM roles when possible** (especially in production)
3. **Regularly rotate access keys**
4. **Use least-privilege IAM policies**

Example minimal IAM policy:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            "Resource": "*"
        }
    ]
}
```

## Next Steps

After successful setup:
1. Try different models to find the best fit for your use case
2. Experiment with the various parameters (temperature, max_tokens, etc.)
3. Consider using different models for different tasks (planning vs. code generation)
4. Monitor costs and optimize your usage patterns

Your AWS Bedrock integration is now ready! 🎉
