# pdf2markdown

Using VLMs to transform codeforces-polygon style problems into markdown + Mathjax format.

## Quick start

### Installing dependencies

```bash
pip install pdf2image pillow requests

# Ubuntu/Debian:
sudo apt-get install poppler-utils

# macOS:
brew install poppler
```

### Basic usage

```bash
# For single file
python main.py single
# for multiple files
python main.py batch
```

## Configs

### config.json example:

`config.json`：

supporting any openai api style VLMs.

```json
{
    "api_settings": {
        "openai": {
            "api_key": "sk-your-openai-key",
            "api_base": "https://api.openai.com/v1",
            "model": "gpt-4-vision-preview"
        },
        "claude": {
            "api_key": "claude-your-key", 
            "api_base": "https://api.anthropic.com/v1",
            "model": "claude-3-sonnet-20240229"
        },
        "qwen": {
            "api_key": "sk-your-qwen-key",
            "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen-vl-plus"
        }
    },
    "competition_settings": {
        "dpi": 400,
        "delay_between_pages": 2,
        "max_tokens": 3000,
        "timeout": 60,
        "auto_split_problems": true,
        "generate_index": true,
        "validate_latex": true
    }
}
```

### Prompts

change `extract_content_from_image` prompts to fit your needs!

```python
# prompts for math problems in Chinese
math_prompt = """请提取这张图片中的数学题目，要求：
1. 保持题目编号和结构
2. 所有数学公式使用LaTeX格式
3. 几何图形用文字描述
4. 保持解答步骤的逻辑顺序
"""

# prompts for choosing problems in Chinese
mcq_prompt = """请提取选择题内容，要求：
1. 保持A、B、C、D选项格式
2. 标记正确答案（如果可见）
3. 公式使用LaTeX格式
4. 保持题目的完整性
"""
```