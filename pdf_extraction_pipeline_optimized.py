#!/usr/bin/env python3
"""
PDF题目提取Pipeline (超级优化版)
混合使用文本提取和LLM处理，大幅提升效率
- 优先使用PDF文本直接提取
- 对无法提取或质量不佳的页面使用LLM
- 特别优化样例数据的提取精度
"""

import os
import base64
import json
import time
import re
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import argparse

try:
    import pdf2image
    from PIL import Image
    import requests
    from pdf2image import convert_from_path
    import pdfplumber
    import PyPDF2
except ImportError as e:
    print(f"请安装必要的依赖: pip install pdf2image pillow requests pdfplumber PyPDF2")
    print(f"还需要安装poppler: ")
    print(f"  Ubuntu/Debian: sudo apt-get install poppler-utils")
    print(f"  macOS: brew install poppler")
    print(f"  Windows: 下载poppler二进制文件")
    exit(1)

class OptimizedPDFExtractionPipeline:
    def __init__(self, api_key: str, api_base: str = "https://api.openai.com/v1", model: str = "gpt-4-vision-preview", use_cache: bool = True):
        """
        初始化优化版PDF提取pipeline
        
        Args:
            api_key: LLM API密钥
            api_base: API基础URL
            model: 使用的模型名称
            use_cache: 是否使用缓存
        """
        self.api_key = api_key
        self.api_base = api_base
        self.model = model
        self.use_cache = use_cache
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # 缓存和页面目录
        self.cache_dir = "cache"
        self.pages_dir = "pages"
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.pages_dir, exist_ok=True)
        
        # 统计信息
        self.stats = {
            "text_extracted_pages": 0,
            "llm_processed_pages": 0,
            "cached_pages": 0,
            "total_pages": 0
        }

    def extract_text_from_pdf(self, pdf_path: str) -> List[Dict[str, str]]:
        """
        尝试直接从PDF提取文本
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            List[Dict]: 每页的文本内容和质量评估
        """
        pages_data = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    
                    if page_text:
                        # 评估文本质量
                        quality_score = self.evaluate_text_quality(page_text)
                        
                        pages_data.append({
                            "page_num": i + 1,
                            "text": page_text,
                            "quality": quality_score,
                            "extraction_method": "direct_text"
                        })
                    else:
                        pages_data.append({
                            "page_num": i + 1,
                            "text": "",
                            "quality": 0.0,
                            "extraction_method": "needs_llm"
                        })
                        
        except Exception as e:
            print(f"PDF文本提取失败: {e}")
            return []
            
        return pages_data

    def evaluate_text_quality(self, text: str) -> float:
        """
        评估提取文本的质量
        
        Args:
            text: 提取的文本
            
        Returns:
            float: 质量分数 (0-1)
        """
        if not text or len(text.strip()) < 20:
            return 0.0
        
        quality_indicators = 0
        total_checks = 6
        
        # 检查1: 包含问题标识
        if re.search(r'Problem\s+[A-Z]\.?', text, re.IGNORECASE):
            quality_indicators += 1
            
        # 检查2: 包含输入输出格式
        if re.search(r'(Input|Output|input|output)', text):
            quality_indicators += 1
            
        # 检查3: 包含时间/内存限制
        if re.search(r'(Time limit|Memory limit|time|memory)', text, re.IGNORECASE):
            quality_indicators += 1
            
        # 检查4: 包含样例
        if re.search(r'(Example|Sample|standard|input|output)', text, re.IGNORECASE):
            quality_indicators += 1
            
        # 检查5: 文本长度合理
        if 100 <= len(text) <= 5000:
            quality_indicators += 1
            
        # 检查6: 没有太多乱码
        non_ascii_ratio = len([c for c in text if ord(c) > 127]) / len(text)
        if non_ascii_ratio < 0.3:  # 允许30%的非ASCII字符（中文等）
            quality_indicators += 1
        
        return quality_indicators / total_checks

    def convert_text_to_markdown(self, text: str, page_num: int) -> str:
        """
        将提取的文本转换为标准markdown格式
        
        Args:
            text: 原始文本
            page_num: 页码
            
        Returns:
            str: 格式化的markdown内容
        """
        # 基础清理
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                cleaned_lines.append(line)
        
        if not cleaned_lines:
            return ""
        
        markdown_content = []
        
        # 处理每一行
        i = 0
        while i < len(cleaned_lines):
            line = cleaned_lines[i]
            
            # 识别问题标题
            if re.match(r'^Problem\s+[A-Z]\.?\s*', line, re.IGNORECASE):
                # 提取问题编号和标题
                match = re.match(r'^Problem\s+([A-Z])\.?\s*(.*)', line, re.IGNORECASE)
                if match:
                    problem_id = match.group(1)
                    problem_title = match.group(2).strip()
                    if not problem_title and i + 1 < len(cleaned_lines):
                        # 标题可能在下一行
                        problem_title = cleaned_lines[i + 1].strip()
                        i += 1
                    
                    markdown_content.append(f"## Problem {problem_id}. {problem_title}")
                else:
                    markdown_content.append(f"## {line}")
            
            # 识别文件输入输出
            elif 'Input file:' in line or 'Output file:' in line:
                markdown_content.append(f"**{line}**")
            
            # 识别限制条件
            elif 'Time limit:' in line or 'Memory limit:' in line:
                markdown_content.append(f"**{line}**")
            
            # 识别样例部分
            elif re.match(r'^(Example|Sample)', line, re.IGNORECASE):
                markdown_content.append(f"\n### {line}")
                
                # 查找样例数据
                sample_lines = []
                j = i + 1
                while j < len(cleaned_lines):
                    next_line = cleaned_lines[j]
                    
                    # 如果遇到Note或下一个部分，停止
                    if re.match(r'^(Note|Problem|Input|Output)', next_line, re.IGNORECASE):
                        break
                    
                    sample_lines.append(next_line)
                    j += 1
                
                # 处理样例数据
                if sample_lines:
                    markdown_content.append("\n**Input:**")
                    markdown_content.append("```")
                    
                    # 分离输入输出
                    input_lines = []
                    output_lines = []
                    
                    # 简单的样例数据分离逻辑
                    current_section = "input"
                    for sample_line in sample_lines:
                        if re.match(r'^(standard\s+input|standard\s+output)', sample_line, re.IGNORECASE):
                            continue
                        
                        # 尝试识别输出开始（通常是重复的数据或特定格式）
                        if current_section == "input":
                            input_lines.append(sample_line)
                            # 简单的启发式：如果这行看起来像输出结果，切换到输出
                            if len(input_lines) > 1 and self.looks_like_output(sample_line):
                                output_lines.append(input_lines.pop())
                                current_section = "output"
                        else:
                            output_lines.append(sample_line)
                    
                    # 输出输入部分
                    for line in input_lines:
                        markdown_content.append(line)
                    
                    markdown_content.append("```")
                    
                    # 输出输出部分
                    if output_lines:
                        markdown_content.append("\n**Output:**")
                        markdown_content.append("```")
                        for line in output_lines:
                            markdown_content.append(line)
                        markdown_content.append("```")
                
                i = j - 1
            
            # 识别Note部分
            elif line.startswith('Note'):
                markdown_content.append(f"\n### {line}")
            
            # 普通内容
            else:
                # 检查是否是数学表达式
                if re.search(r'\b\d+\s*[\+\-\*/]\s*\d+\b|[A-Za-z]\s*=\s*\d+', line):
                    # 可能包含数学内容，用$包围数字和变量
                    formatted_line = self.format_math_content(line)
                    markdown_content.append(formatted_line)
                else:
                    markdown_content.append(line)
            
            i += 1
        
        return '\n'.join(markdown_content)

    def looks_like_output(self, line: str) -> bool:
        """判断一行文本是否看起来像输出"""
        # 简单的启发式规则
        # 如果只包含数字和空格，且数字较少，可能是输出
        if re.match(r'^[\d\s\-]+$', line) and len(line.strip().split()) <= 5:
            return True
        return False

    def format_math_content(self, text: str) -> str:
        """格式化数学内容"""
        # 简单的数学格式化
        # 用$包围单独的变量和数字
        formatted = re.sub(r'\b([a-zA-Z])\b', r'$\1$', text)
        formatted = re.sub(r'\b(\d+)\b', r'$\1$', formatted)
        return formatted

    def get_image_hash(self, image_path: str) -> str:
        """计算图片的SHA256哈希值"""
        try:
            with open(image_path, 'rb') as f:
                content = f.read()
                return hashlib.sha256(content).hexdigest()
        except Exception as e:
            print(f"计算图片哈希值失败: {e}")
            return ""

    def load_from_cache(self, image_path: str) -> Optional[str]:
        """从缓存加载LLM处理结果"""
        if not self.use_cache:
            return None
        
        hash_value = self.get_image_hash(image_path)
        if not hash_value:
            return None
        
        cache_file = os.path.join(self.cache_dir, f"{hash_value}.json")
        
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    return cache_data.get('content')
        except Exception as e:
            print(f"读取缓存失败: {e}")
        
        return None

    def save_to_cache(self, image_path: str, content: str):
        """保存LLM处理结果到缓存"""
        if not self.use_cache:
            return
        
        hash_value = self.get_image_hash(image_path)
        if not hash_value:
            return
        
        cache_file = os.path.join(self.cache_dir, f"{hash_value}.json")
        
        try:
            cache_data = {
                'content': content,
                'timestamp': time.time(),
                'image_path': image_path
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存缓存失败: {e}")

    def encode_image_to_base64(self, image_path: str) -> str:
        """将图片编码为base64格式"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            print(f"图片编码失败: {e}")
            return ""

    def extract_content_from_image(self, image_path: str, page_num: int, total_pages: int) -> Optional[str]:
        """使用LLM从图片中提取内容"""
        print(f"正在用LLM处理图片: {image_path} (第{page_num}/{total_pages}页)")
        
        # 首先尝试从缓存加载
        cached_content = self.load_from_cache(image_path)
        if cached_content:
            print(f"第{page_num}页LLM内容从缓存加载完成 ({len(cached_content)} 字符)")
            self.stats["cached_pages"] += 1
            return cached_content
        
        # 编码图片  
        base64_image = self.encode_image_to_base64(image_path)
        
        # 针对算法竞赛题目的优化提示词
        competition_prompt = f"""请仔细分析这张算法竞赛题目图片，精确提取所有内容。这是第{page_num}页(共{total_pages}页)。

**重要提示：请完整提取页面上的所有文本内容，特别注意样例数据的格式！**

**识别规则:**
1. **新题目识别**: 
   - 仅当页面上有明显的题目开始标记(如"Problem X")并且有题目描述时，才使用 ## Problem X. 题目名称 格式

2. **样例格式(极其关键)**:
   - 样例数据必须完全按原始格式输出，保持所有空格、换行和对齐
   - 使用以下格式：
   ```
   具体的输入/输出数据（完全按原样，不要改变任何字符）
   ```

3. **数学公式**: 使用LaTeX格式 $formula$

4. **完整提取**: 不要遗漏任何内容，包括限制条件、注释等

请直接输出markdown格式内容，不要添加任何额外说明。"""
        
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
            "max_tokens": 8000
        }
        
        # 发送请求
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{self.api_base}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result['choices'][0]['message']['content']
                    print(f"第{page_num}页LLM处理完成 ({len(content)} 字符)")
                    
                    # 保存到缓存
                    self.save_to_cache(image_path, content)
                    self.stats["llm_processed_pages"] += 1
                    
                    return content
                else:
                    print(f"LLM请求失败: {response.status_code}")
                    if attempt < max_retries - 1:
                        time.sleep(5)
                    
            except Exception as e:
                print(f"LLM处理出错: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)
        
        return None

    def convert_pdf_to_images(self, pdf_path: str, dpi: int = 300) -> List[str]:
        """将PDF转换为图片"""
        try:
            print(f"开始转换PDF为图片 (DPI: {dpi})")
            
            images = convert_from_path(pdf_path, dpi=dpi)
            image_paths = []
            
            for i, image in enumerate(images):
                image_path = os.path.join(self.pages_dir, f"page_{i+1:03d}.png")
                image.save(image_path, 'PNG')
                image_paths.append(image_path)
                print(f"第 {i+1} 页转换完成: {image_path}")
            
            print(f"PDF转换完成，共 {len(image_paths)} 页")
            return image_paths
            
        except Exception as e:
            print(f"PDF转换失败: {e}")
            return []

    def process_pdf_optimized(self, pdf_path: str, output_file: str, debug: bool = False) -> bool:
        """
        优化版PDF处理主函数
        混合使用文本提取和LLM处理
        """
        print(f"🚀 开始优化处理PDF: {pdf_path}")
        print("=" * 60)
        
        # 重置统计
        self.stats = {k: 0 for k in self.stats}
        
        # 步骤1: 尝试直接提取文本
        print("📝 步骤1: 尝试直接提取PDF文本...")
        pages_text_data = self.extract_text_from_pdf(pdf_path)
        
        if not pages_text_data:
            print("❌ 文本提取失败，回退到纯LLM模式")
            return self.fallback_to_llm_only(pdf_path, output_file, debug)
        
        self.stats["total_pages"] = len(pages_text_data)
        
        # 步骤2: 决定每页的处理方式
        print("🧠 步骤2: 分析每页最佳处理方式...")
        processing_plan = []
        
        for page_data in pages_text_data:
            page_num = page_data["page_num"]
            quality = page_data["quality"]
            
            if quality >= 0.6:  # 文本质量足够好
                processing_plan.append({
                    "page_num": page_num,
                    "method": "text_only",
                    "quality": quality
                })
                print(f"  第{page_num}页: 文本提取 (质量: {quality:.2f})")
            else:
                processing_plan.append({
                    "page_num": page_num, 
                    "method": "llm_required",
                    "quality": quality
                })
                print(f"  第{page_num}页: 需要LLM处理 (质量: {quality:.2f})")
        
        # 步骤3: 执行处理计划
        print("⚙️  步骤3: 执行混合处理...")
        
        all_contents = []
        image_paths = []
        
        # 只为需要LLM处理的页面生成图片
        llm_pages = [p for p in processing_plan if p["method"] == "llm_required"]
        if llm_pages:
            print(f"📸 为{len(llm_pages)}页生成图片...")
            image_paths = self.convert_pdf_to_images(pdf_path)
        
        # 处理每页
        for i, plan in enumerate(processing_plan):
            page_num = plan["page_num"]
            method = plan["method"]
            
            if method == "text_only":
                # 直接使用提取的文本
                page_data = pages_text_data[i]
                markdown_content = self.convert_text_to_markdown(page_data["text"], page_num)
                all_contents.append(markdown_content)
                self.stats["text_extracted_pages"] += 1
                print(f"✅ 第{page_num}页文本处理完成 ({len(markdown_content)} 字符)")
                
            else:
                # 使用LLM处理
                if i < len(image_paths):
                    image_path = image_paths[i]
                    llm_content = self.extract_content_from_image(image_path, page_num, len(processing_plan))
                    if llm_content:
                        all_contents.append(llm_content)
                    else:
                        print(f"⚠️  第{page_num}页LLM处理失败")
                        all_contents.append("")
        
        # 步骤4: 合并内容
        print("🔗 步骤4: 合并题目内容...")
        final_content = self.merge_problem_content(all_contents, debug)
        
        # 步骤5: 保存结果
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(final_content)
            print(f"✅ 处理完成! 输出文件: {output_file}")
            
            # 输出统计信息
            print("\n📊 处理统计:")
            print(f"  总页数: {self.stats['total_pages']}")
            print(f"  文本提取: {self.stats['text_extracted_pages']} 页")
            print(f"  LLM处理: {self.stats['llm_processed_pages']} 页")
            print(f"  缓存命中: {self.stats['cached_pages']} 页")
            
            efficiency = (self.stats['text_extracted_pages'] + self.stats['cached_pages']) / self.stats['total_pages'] * 100
            print(f"  处理效率: {efficiency:.1f}% (无需新LLM调用)")
            
            return True
            
        except Exception as e:
            print(f"❌ 保存文件失败: {e}")
            return False

    def fallback_to_llm_only(self, pdf_path: str, output_file: str, debug: bool = False) -> bool:
        """回退到纯LLM模式"""
        print("🔄 回退到纯LLM处理模式...")
        
        # 导入原有的处理管道
        from pdf_extraction_pipeline import PDFExtractionPipeline
        
        old_pipeline = PDFExtractionPipeline(self.api_key, self.api_base, self.model, self.use_cache)
        return old_pipeline.process_pdf(pdf_path, output_file, debug)

    def merge_problem_content(self, contents: List[str], debug: bool = False) -> str:
        """合并问题内容"""
        if not contents:
            return ""
        
        # 简化的合并逻辑
        merged_content = []
        current_problem = []
        
        problem_pattern = re.compile(r'^##\s*Problem\s+\w+\.')
        
        for content in contents:
            if not content.strip():
                continue
                
            lines = content.split('\n')
            
            for line in lines:
                if problem_pattern.match(line):
                    # 发现新问题，保存当前问题
                    if current_problem:
                        merged_content.append('\n'.join(current_problem))
                        current_problem = []
                    current_problem.append(line)
                else:
                    current_problem.append(line)
        
        # 保存最后一个问题
        if current_problem:
            merged_content.append('\n'.join(current_problem))
        
        return '\n\n'.join(merged_content)

# 添加命令行接口
def main():
    parser = argparse.ArgumentParser(description='优化版PDF算法竞赛题目提取工具')
    parser.add_argument('pdf_file', help='输入PDF文件路径')
    parser.add_argument('-o', '--output', default='extracted_content.md', help='输出markdown文件路径')
    parser.add_argument('-k', '--api-key', required=True, help='LLM API密钥')
    parser.add_argument('-b', '--api-base', default='https://dashscope.aliyuncs.com/compatible-mode/v1', help='API基础URL')
    parser.add_argument('-m', '--model', default='qwen-vl-max', help='使用的模型')
    parser.add_argument('--no-cache', action='store_true', help='禁用缓存')
    parser.add_argument('-d', '--debug', action='store_true', help='启用调试模式')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.pdf_file):
        print(f"❌ PDF文件不存在: {args.pdf_file}")
        return False
    
    # 初始化优化版pipeline
    pipeline = OptimizedPDFExtractionPipeline(
        api_key=args.api_key,
        api_base=args.api_base,
        model=args.model,
        use_cache=not args.no_cache
    )
    
    # 处理PDF
    success = pipeline.process_pdf_optimized(args.pdf_file, args.output, args.debug)
    
    if success:
        print("🎉 处理完成!")
        return True
    else:
        print("❌ 处理失败!")
        return False

if __name__ == "__main__":
    main()
