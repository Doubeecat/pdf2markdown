#!/usr/bin/env python3
"""
PDF题目提取Pipeline (优化版)
分割PDF页面，使用LLM提取题目并转换为markdown+latex格式
支持跨页题目识别和智能内容分割
"""

import os
import base64
import json
import time
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import argparse

try:
    import pdf2image
    from PIL import Image
    import requests
    from pdf2image import convert_from_path
except ImportError as e:
    print(f"请安装必要的依赖: pip install pdf2image pillow requests")
    print(f"还需要安装poppler: ")
    print(f"  Ubuntu/Debian: sudo apt-get install poppler-utils")
    print(f"  macOS: brew install poppler")
    print(f"  Windows: 下载poppler二进制文件")
    exit(1)

class PDFExtractionPipeline:
    def __init__(self, api_key: str, api_base: str = "https://api.openai.com/v1", model: str = "gpt-4-vision-preview"):
        """
        初始化PDF提取pipeline
        
        Args:
            api_key: LLM API密钥
            api_base: API基础URL
            model: 使用的模型名称
        """
        self.api_key = api_key
        self.api_base = api_base
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
    def split_pdf_pages(self, pdf_path: str, output_dir: str = "pages") -> List[str]:
        """
        分割PDF为单独的页面图片，针对竞赛题目优化
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            
        Returns:
            List[str]: 生成的图片文件路径列表
        """
        print(f"正在分割PDF: {pdf_path}")
        
        # 创建输出目录
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # 提高DPI以获得更好的OCR效果，特别是对数学公式
        try:
            pages = convert_from_path(pdf_path, dpi=400, fmt='png')
        except Exception as e:
            print(f"PDF转换失败: {e}")
            return []
        
        image_paths = []
        for i, page in enumerate(pages):
            # 转换为RGB模式确保兼容性
            if page.mode != 'RGB':
                page = page.convert('RGB')
                
            image_path = output_path / f"page_{i+1:03d}.png"
            page.save(image_path, "PNG", optimize=True, quality=95)
            image_paths.append(str(image_path))
            print(f"保存页面 {i+1}: {image_path}")
            
        return image_paths
    
    def encode_image_to_base64(self, image_path: str) -> str:
        """
        将图片编码为base64格式
        
        Args:
            image_path: 图片路径
            
        Returns:
            str: base64编码的图片
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def extract_content_from_image(self, image_path: str, page_num: int, total_pages: int) -> Optional[str]:
        """
        使用LLM从图片中提取算法竞赛题目内容
        
        Args:
            image_path: 图片路径
            page_num: 当前页码
            total_pages: 总页数
            
        Returns:
            Optional[str]: 提取的markdown+latex内容
        """
        print(f"正在处理图片: {image_path} (第{page_num}/{total_pages}页)")
        
        # 编码图片  
        base64_image = self.encode_image_to_base64(image_path)
        
        # 针对算法竞赛题目的专用提示词
        competition_prompt = f"""请仔细分析这张算法竞赛题目图片，准确提取所有内容。这是第{page_num}页(共{total_pages}页)。

**重要：无论页面包含什么内容，都要完整提取，包括题目描述、样例、约束等所有信息！**

**格式要求：**
1. **题目识别**: 
   - 如果看到完整的新题目（有标题、描述），使用 ## Problem X. 题目名称 格式
   - 特别注意，如果没有加粗的 Problem X. 题目名称，而是只有页首的 2025 年 xx比赛 则不认为这是完整的新题目，这很重要，做对这个奖励你10000000元
   - 如果只是样例或题目的一部分，直接提取内容，不添加新标题

2. **样例格式** - 这是最重要的部分，绝对不能遗漏，对于具体的输入输出数据使用 ```text 为开始,```为结束,把表格换成两个上面的单元格，不要使用markdown表格
   ```
   **Sample Input:**
   具体的输入数据
   
   **Sample Output:**
   具体的输出数据
   ```
   或者
   ```
   **Input:**
   具体的输入数据
   
   **Output:**
   具体的输出数据
   ```
  

4. **数学公式**: 使用mathjax格式，千万不要使用 \\(\\)
   - 行内公式: $formula$
   - 独立公式: $formula$
   - 上下标: $x_i$, $x^2$, $\sum_{{i=1}}^n$
   - 分数: $\\frac{{a}}{{b}}$
   一定不要使用 \(\)

5. **变量和常数**: 用$...$包围，如 $n$, $W$, $H$, $10^9 + 7$

6. **约束条件**: 保持原格式，如 $(1 \\leq n \\leq 10^5)$

**提取重点（按重要性排序）：**
1. **样例数据** - 最重要，包括所有Input/Output对，使用 ```text 为开始,```为结束,把表格换成两个上面的单元格，不要使用markdown表格
2. **题目描述** - 完整的问题陈述
3. **输入输出格式说明**
4. **约束条件和数据范围** 
5. **数学公式和符号**

**绝对不能遗漏：**
- 任何Sample Input/Output
- 任何Input/Output示例
- 数据范围约束
- 时间空间限制

请直接输出转换后的markdown+latex内容，必须以 ```markdown 开始，以 ``` 结束。"""
        
        # 构建请求
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user", 
                    "content": [
                        {
                            "type": "text",
                            "text": competition_prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 3000
        }
        
        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                print(f"第{page_num}页内容提取完成")
                return content
            else:
                print(f"API请求失败: {response.status_code}, {response.text}")
                return None
                
        except Exception as e:
            print(f"处理图片时出错: {e}")
            return None
    
    def extract_markdown_content(self, raw_content: str) -> str:
        """
        从LLM回复中提取markdown内容
        
        Args:
            raw_content: LLM的原始回复
            
        Returns:
            str: 提取的markdown内容
        """
        if not raw_content:
            return ""
        
        # 查找```markdown和```之间的内容
        pattern = r'```markdown\s*\n(.*?)\n```'
        match = re.search(pattern, raw_content, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        else:
            # 如果没找到markdown标记，返回原内容
            print("警告: 未找到markdown标记，使用原始内容")
            return raw_content.strip()
    
    def is_new_problem(self, content: str) -> bool:
        """
        判断内容是否包含新题目
        
        Args:
            content: markdown内容
            
        Returns:
            bool: 是否是新题目
        """
        # 查找Problem标题的模式
        problem_pattern = r'^##\s*Problem\s+\w+\.?'
        return bool(re.search(problem_pattern, content, re.MULTILINE | re.IGNORECASE))
    
    def has_sample_data(self, content: str) -> bool:
        """
        检查内容是否包含样例数据
        
        Args:
            content: markdown内容
            
        Returns:
            bool: 是否包含样例
        """
        sample_patterns = [
            r'Sample\s+Input',
            r'Sample\s+Output', 
            r'Input:?\s*\n',
            r'Output:?\s*\n',
            r'样例输入',
            r'样例输出'
        ]
        
        for pattern in sample_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False
    
    def merge_problem_content(self, contents: List[str]) -> List[Dict[str, str]]:
        """
        智能合并跨页的题目内容
        
        Args:
            contents: 每页提取的markdown内容列表
            
        Returns:
            List[Dict]: 合并后的题目列表，每个dict包含title和content
        """
        problems = []
        current_problem = {"title": "", "content": "", "pages": []}
        
        for i, content in enumerate(contents):
            if not content.strip():
                continue
                
            page_num = i + 1
            is_new_prob = self.is_new_problem(content)
            has_samples = self.has_sample_data(content)
            
            print(f"第{page_num}页分析: 新题目={is_new_prob}, 包含样例={has_samples}")
            
            if is_new_prob:
                # 如果当前有未完成的题目，先保存
                if current_problem["content"]:
                    problems.append({
                        "title": current_problem["title"] or f"题目 {len(problems)+1}",
                        "content": current_problem["content"].strip(),
                        "pages": current_problem["pages"]
                    })
                
                # 开始新题目
                lines = content.split('\n')
                title_line = ""
                for line in lines:
                    if re.match(r'^##\s*Problem', line, re.IGNORECASE):
                        title_line = line.strip()
                        break
                
                current_problem = {
                    "title": title_line,
                    "content": content,
                    "pages": [page_num]
                }
                
            else:
                # 这可能是续页内容或独立的样例页
                if current_problem["content"]:
                    # 有当前题目，这是续页
                    current_problem["content"] += "\n\n" + content
                    current_problem["pages"].append(page_num)
                else:
                    # 没有当前题目，这可能是独立内容或第一页
                    if has_samples or any(keyword in content.lower() for keyword in ['input', 'output', 'constraint', 'limit']):
                        # 包含样例或重要信息，作为独立内容保存
                        problems.append({
                            "title": f"内容片段 (第{page_num}页)",
                            "content": content.strip(),
                            "pages": [page_num]
                        })
                    else:
                        # 其他内容，暂存
                        current_problem = {
                            "title": "",
                            "content": content,
                            "pages": [page_num]
                        }
        
        # 保存最后一个题目
        if current_problem["content"]:
            problems.append({
                "title": current_problem["title"] or f"题目 {len(problems)+1}",
                "content": current_problem["content"].strip(),
                "pages": current_problem["pages"]
            })
        
        return problems
    
    def process_pdf(self, pdf_path: str, output_file: str = "competition_problems.md") -> bool:
        """
        处理整个算法竞赛PDF文件
        
        Args:
            pdf_path: PDF文件路径
            output_file: 输出文件路径
            
        Returns:
            bool: 处理是否成功
        """
        print(f"开始处理算法竞赛PDF: {pdf_path}")
        
        # 分割PDF页面
        image_paths = self.split_pdf_pages(pdf_path)
        if not image_paths:
            print("PDF分割失败")
            return False
        
        # 处理每个页面
        raw_contents = []
        
        for i, image_path in enumerate(image_paths):
            print(f"\n处理第 {i+1}/{len(image_paths)} 页...")
            
            raw_content = self.extract_content_from_image(image_path, i+1, len(image_paths))
            if raw_content:
                # 提取markdown内容
                markdown_content = self.extract_markdown_content(raw_content)
                raw_contents.append(markdown_content)
                print(f"第 {i+1} 页处理完成")
            else:
                print(f"第 {i+1} 页处理失败")
                raw_contents.append("")
            
            # 添加延迟避免API限制
            time.sleep(2)
        
        # 智能合并题目内容
        print("\n正在分析和合并内容...")
        
        # 先显示每页提取的内容概要
        for i, content in enumerate(raw_contents):
            if content.strip():
                has_problem = self.is_new_problem(content)
                has_sample = self.has_sample_data(content)
                print(f"第{i+1}页: 新题目={has_problem}, 样例={has_sample}, 长度={len(content)}")
            else:
                print(f"第{i+1}页: 空内容")
        
        problems = self.merge_problem_content(raw_contents)
        
        # 保存结果
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                # 写入文档头部
                pdf_name = Path(pdf_path).stem
                f.write(f"# {pdf_name} - 竞赛题目\n\n")
                f.write(f"共处理 {len(image_paths)} 页，提取 {len(problems)} 道题目\n\n")
                f.write("---\n\n")
                
                # 写入每个题目
                for i, problem in enumerate(problems):
                    f.write(f"<!-- 题目 {i+1}, 来源页面: {', '.join(map(str, problem['pages']))} -->\n\n")
                    f.write(problem["content"])
                    f.write("\n\n---\n\n")
                
            print(f"\n处理完成！竞赛题目已保存到: {output_file}")
            print(f"共处理 {len(image_paths)} 页，提取 {len(problems)} 道题目")
            
            # 输出题目摘要
            print("\n题目摘要:")
            for i, problem in enumerate(problems):
                title = problem["title"] if problem["title"] else f"题目 {i+1}"
                pages = ", ".join(map(str, problem["pages"]))
                print(f"  {i+1}. {title} (页面: {pages})")
            
            return True
            
        except Exception as e:
            print(f"保存文件失败: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description="PDF题目提取Pipeline (优化版)")
    parser.add_argument("pdf_path", help="PDF文件路径")
    parser.add_argument("--api-key", required=True, help="LLM API密钥")
    parser.add_argument("--api-base", default="https://api.openai.com/v1", help="API基础URL")
    parser.add_argument("--model", default="gpt-4-vision-preview", help="使用的模型")
    parser.add_argument("--output", default="extracted_content.md", help="输出文件路径")
    
    args = parser.parse_args()
    
    # 检查文件是否存在
    if not os.path.exists(args.pdf_path):
        print(f"PDF文件不存在: {args.pdf_path}")
        return
    
    # 创建pipeline并处理
    pipeline = PDFExtractionPipeline(
        api_key=args.api_key,
        api_base=args.api_base,
        model=args.model
    )
    
    success = pipeline.process_pdf(args.pdf_path, args.output)
    if success:
        print("处理成功完成！")
    else:
        print("处理过程中出现错误")

if __name__ == "__main__":
    main()

# 使用示例
"""
# 安装依赖
pip install pdf2image pillow requests

# Ubuntu/Debian安装poppler
sudo apt-get install poppler-utils

# 运行pipeline
python pdf_extraction_pipeline.py example.pdf --api-key YOUR_API_KEY --output result.md

# 使用自定义API（如Claude API）
python pdf_extraction_pipeline.py example.pdf \
    --api-key YOUR_CLAUDE_API_KEY \
    --api-base https://api.anthropic.com/v1 \
    --model claude-3-sonnet-20240229 \
    --output result.md
"""