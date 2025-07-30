# pdf2markdown

## 🏆 专门优化算法竞赛题目处理

这个pipeline专门针对算法竞赛题目进行了优化，能够：
- 🔍 准确识别复杂数学公式和符号
- 📊 保持题目的标准格式结构  
- 🧮 正确处理上下标、分数、求和符号等
- 📝 维持Input/Output格式和样例数据
- ⏱️ 提取时间空间复杂度限制

## 功能特性

- 📄 高精度PDF页面分割（400 DPI）
- 🤖 专业竞赛题目识别和格式化
- 📝 LaTeX数学公式标准化输出
- 🔧 支持多种LLM API
- 📚 自动题目分割和索引生成
- ✅ LaTeX语法验证

## 快速开始

### 安装依赖

```bash
# 安装Python包
pip install pdf2image pillow requests

# 安装系统依赖
# Ubuntu/Debian:
sudo apt-get install poppler-utils

# macOS:
brew install poppler
```

### 基础使用

```bash
# 处理单个竞赛PDF
python pdf_extraction_pipeline.py contest.pdf \
    --api-key YOUR_API_KEY \
    --output contest_problems.md

# 使用竞赛专用工具处理
python competition_tools.py single contest.pdf \
    --api-key YOUR_API_KEY

# 批处理多个竞赛PDF
python competition_tools.py batch ./contest_pdfs \
    --api-key YOUR_API_KEY \
    --output ./contests
```

## 高级配置

### API配置示例

创建 `config.json`：

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

### 使用配置文件

```python
import json
from pdf_extraction_pipeline import PDFExtractionPipeline

# 加载配置
with open('config.json', 'r') as f:
    config = json.load(f)

# 使用配置创建pipeline
api_config = config['api_settings']['openai']  # 或其他API
pipeline = PDFExtractionPipeline(
    api_key=api_config['api_key'],
    api_base=api_config['api_base'],
    model=api_config['model']
)
```

## 竞赛题目处理工具

### 自动题目分割

```bash
# 分割已处理的markdown文件为单独题目
python cp_tools.py split contest_problems.md --output ./problems

# 生成的文件结构：
# problems/
# ├── Problem_A.md
# ├── Problem_B.md
# ├── Problem_C.md
# └── ...
```

### 批量处理多个竞赛

```bash
# 批处理整个目录
python cp_tools.py batch ./contest_pdfs --api-key YOUR_KEY
```

### 题目索引生成

```bash
# 为题目目录生成索引
python competition_tools.py index ./problems --output index.md
```

## LaTeX公式处理

### 支持的公式类型

- **基本符号**: $\leq$, $\geq$, $\neq$, $\times$, $\cdot$
- **上下标**: $x_i$, $x^2$, $a_{i,j}^{(k)}$
- **分数**: $\frac{a}{b}$, $\frac{p}{q}$
- **求和乘积**: $\sum_{i=1}^n$, $\prod_{i=1}^n$
- **复杂公式**: $\binom{n}{k}$, $\lfloor x \rfloor$, $\lceil x \rceil$

### 公式验证

```python
from competition_tools import CompetitionProblemProcessor

processor = CompetitionProblemProcessor()

# 验证LaTeX语法
with open('problem.md', 'r') as f:
    content = f.read()

errors = processor.validate_latex(content)
if errors:
    print("发现LaTeX错误:")
    for error in errors:
        print(f"  - {error}")
```

### 自定义提示词

修改 `extract_content_from_image` 方法中的提示词来适应特定需求：

```python
# 针对数学题目的提示词
math_prompt = """请提取这张图片中的数学题目，要求：
1. 保持题目编号和结构
2. 所有数学公式使用LaTeX格式
3. 几何图形用文字描述
4. 保持解答步骤的逻辑顺序
"""

# 针对选择题的提示词
mcq_prompt = """请提取选择题内容，要求：
1. 保持A、B、C、D选项格式
2. 标记正确答案（如果可见）
3. 公式使用LaTeX格式
4. 保持题目的完整性
"""
```