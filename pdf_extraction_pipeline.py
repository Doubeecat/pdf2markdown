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
import hashlib
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
    def __init__(self, api_key: str, api_base: str = "https://api.openai.com/v1", model: str = "gpt-4-vision-preview", use_cache: bool = True):
        """
        初始化PDF提取pipeline
        
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
        
        # 创建缓存目录
        self.cache_dir = "cache"
        if self.use_cache:
            os.makedirs(self.cache_dir, exist_ok=True)
        
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
    
    def get_image_hash(self, image_path: str) -> str:
        """
        计算图片文件的哈希值，用于缓存键
        
        Args:
            image_path: 图片路径
            
        Returns:
            str: 图片文件的SHA256哈希值
        """
        with open(image_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    
    def get_cache_path(self, image_hash: str) -> str:
        """
        获取缓存文件路径
        
        Args:
            image_hash: 图片哈希值
            
        Returns:
            str: 缓存文件路径
        """
        return os.path.join(self.cache_dir, f"{image_hash}.json")
    
    def load_from_cache(self, image_path: str) -> Optional[str]:
        """
        从缓存加载LLM输出
        
        Args:
            image_path: 图片路径
            
        Returns:
            Optional[str]: 缓存的LLM输出，如果不存在则返回None
        """
        if not self.use_cache:
            return None
            
        try:
            image_hash = self.get_image_hash(image_path)
            cache_path = self.get_cache_path(image_hash)
            
            if os.path.exists(cache_path):
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    
                # 检查模型是否匹配
                if cache_data.get('model') == self.model:
                    print(f"从缓存加载: {os.path.basename(image_path)}")
                    return cache_data.get('content')
                else:
                    print(f"缓存模型不匹配，重新处理: {os.path.basename(image_path)}")
                    
        except Exception as e:
            print(f"读取缓存失败: {e}")
            
        return None
    
    def save_to_cache(self, image_path: str, content: str) -> None:
        """
        保存LLM输出到缓存
        
        Args:
            image_path: 图片路径
            content: LLM输出内容
        """
        if not self.use_cache:
            return
            
        try:
            image_hash = self.get_image_hash(image_path)
            cache_path = self.get_cache_path(image_hash)
            
            cache_data = {
                'image_path': image_path,
                'model': self.model,
                'content': content,
                'timestamp': time.time(),
                'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"保存缓存失败: {e}")
    
    def clear_cache(self) -> None:
        """
        清理所有缓存文件
        """
        if not os.path.exists(self.cache_dir):
            return
            
        try:
            import shutil
            shutil.rmtree(self.cache_dir)
            os.makedirs(self.cache_dir, exist_ok=True)
            print("缓存已清理")
        except Exception as e:
            print(f"清理缓存失败: {e}")
    
    def get_cache_info(self) -> Dict[str, int]:
        """
        获取缓存信息
        
        Returns:
            Dict: 包含缓存文件数量和总大小的信息
        """
        if not os.path.exists(self.cache_dir):
            return {"count": 0, "size": 0}
            
        count = 0
        total_size = 0
        
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    count += 1
                    file_path = os.path.join(self.cache_dir, filename)
                    total_size += os.path.getsize(file_path)
        except Exception as e:
            print(f"获取缓存信息失败: {e}")
            
        return {"count": count, "size": total_size}
    
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
        
        # 首先尝试从缓存加载
        cached_content = self.load_from_cache(image_path)
        if cached_content:
            print(f"第{page_num}页内容从缓存加载完成 ({len(cached_content)} 字符)")
            return cached_content
        
        # 编码图片  
        base64_image = self.encode_image_to_base64(image_path)
        
        # 针对算法竞赛题目的优化提示词
        competition_prompt = f"""请仔细分析这张算法竞赛题目图片，精确提取所有内容。这是第{page_num}页(共{total_pages}页)。

**重要提示：请完整提取页面上的所有文本内容，不要遗漏任何部分，尤其是样例和数学公式！**

**识别规则:**
1. **新题目识别**: 
   - 仅当页面上有明显的题目开始标记(如"Problem X")并且有题目描述时，才使用 ## Problem X. 题目名称 格式
   - 注意：只有页首的比赛标题、年份等，不算作题目开始
   - 如果只是题目的延续部分或样例，不要添加新标题，直接提取内容

2. **样例格式(非常关键)**:
   - 所有样例都会以 标准输入，标准输出的表格为格式
   - 样例数据必须保留原始格式，不能改变空格、缩进和换行
   - 使用代码块格式：
   ```text
   具体的输入/输出数据（保持原样）
   ```
   - 样例前标记：**Sample Input:**/**Sample Output:** 或 **Input:**/**Output:**

3. **数学公式**:
   - 使用LaTeX格式：$formula$（行内）或$$formula$$（独立行）
   - 所有变量、常量、算式都用$包围，如$n$、$10^9 + 7$
   - 务必保留所有数学符号，包括求和符号、积分符号等

4. **保留的重要元素**:
   - 题目描述和背景故事
   - 输入输出格式说明
   - 所有样例输入输出
   - 所有约束条件和数据范围
   - 提示、注释和解释
   - 分数设置或时间/空间限制

5. **页面结构**:
   - 保留原始段落结构
   - 保持列表、序号的格式
   - 表格内容完整转换为文本

请直接输出转换后的markdown+latex内容，即使不确定某些内容的含义，也请完整提取原文，不要省略或猜测，不要输出任何其他东西。"""
        
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
        
        # 添加重试机制
        max_retries = 3
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{self.api_base}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=60  # 增加超时时间
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result['choices'][0]['message']['content']
                    print(f"第{page_num}页内容提取完成 ({len(content)} 字符)")
                    
                    # 保存到缓存
                    self.save_to_cache(image_path, content)
                    
                    return content
                elif response.status_code == 429:  # 速率限制
                    retry_delay = 10 * (attempt + 1)  # 递增重试延迟
                    print(f"API 速率限制，{retry_delay}秒后重试...")
                    time.sleep(retry_delay)
                else:
                    print(f"API请求失败: {response.status_code}, {response.text}")
                    if attempt < max_retries - 1:
                        print(f"{retry_delay}秒后重试...")
                        time.sleep(retry_delay)
                    else:
                        return None
                        
            except Exception as e:
                print(f"处理图片时出错: {e}")
                if attempt < max_retries - 1:
                    print(f"{retry_delay}秒后重试...")
                    time.sleep(retry_delay)
                else:
                    return None
        
        return None
    
    def is_new_problem(self, content: str) -> bool:
        """
        判断内容是否包含新题目
        """
        # 查找Problem标题的模式，匹配 ## Problem X. 任意标题
        problem_pattern = r'^##\s*Problem\s+\w+\.'
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
            r'标准输入',
            r'标准输出',
            # 添加表格相关的模式
            r'\|.*\|.*\|',  # 检测markdown表格
            r'```text\s*\n.*\n```',  # 检测代码块中的数据
            r'\d+\s*\n\d+',  # 检测数字数据模式（常见于样例）
            r'^\s*\d+\s+\d+\s*$',  # 检测空格分隔的数字
            # 检测样例输入输出的其他模式
            r'\*\*Sample Input:\*\*',
            r'\*\*Sample Output:\*\*',
            r'\*\*Input:\*\*',
            r'\*\*Output:\*\*',
        ]
        
        for pattern in sample_patterns:
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                return True
        return False
    
    def is_likely_sample_page(self, content: str) -> bool:
        """
        判断页面是否可能包含样例数据（即使没有明确标识）
        
        Args:
            content: markdown内容
            
        Returns:
            bool: 是否可能是样例页面
        """
        # 如果内容很短且主要是数据，可能是样例
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        # 如果行数很少（比如小于10行）且包含数字或表格结构
        if len(lines) <= 10:
            data_patterns = [
                r'^\d+$',  # 纯数字行
                r'^\d+\s+\d+',  # 空格分隔的数字
                r'\|.*\|',  # 表格行
                r'^[\d\s]+$',  # 只包含数字和空格
                r'```text',  # 代码块
            ]
            
            data_line_count = 0
            for line in lines:
                for pattern in data_patterns:
                    if re.search(pattern, line):
                        data_line_count += 1
                        break
            
            # 如果超过一半的行都是数据格式，认为是样例页面
            if data_line_count >= len(lines) * 0.5 and data_line_count >= 2:
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
        current_problem = None

        for i, content in enumerate(contents):
            if not content.strip():
                print(f"第{i+1}页: 空内容，跳过")
                continue

            page_num = i + 1
            is_new_prob = self.is_new_problem(content)
            has_samples = self.has_sample_data(content)
            is_likely_sample = self.is_likely_sample_page(content)

            print(f"第{page_num}页分析: 新题目={is_new_prob}, 包含样例={has_samples}, 可能是样例页={is_likely_sample}")

            if is_new_prob:
                # 如果当前有未完成的题目，先保存
                if current_problem and current_problem["content"]:
                    print(f"保存题目: {current_problem['title']}, 页面: {current_problem['pages']}")
                    problems.append({
                        "title": current_problem["title"] or f"题目 {len(problems)+1}",
                        "content": current_problem["content"].strip(),
                        "pages": current_problem["pages"]
                    })

                # 开始新题目
                title_line = next((line.strip() for line in content.split('\n')
                                   if re.match(r'^##\s*Problem', line, re.IGNORECASE)), "")
                print(f"开始新题目: {title_line}")
                current_problem = {
                    "title": title_line,
                    "content": content,
                    "pages": [page_num]
                }

            else:
                # 非新题目内容
                if current_problem:
                    # 有当前题目，无论是什么内容都合并进去
                    # 这样可以确保样例页面（包括只有表格的）都能正确归到题目下
                    current_problem["content"] += "\n\n" + content
                    current_problem["pages"].append(page_num)
                    print(f"第{page_num}页合并到当前题目: {current_problem['title']}")
                else:
                    # 没有当前题目的情况
                    if has_samples or is_likely_sample or any(kw in content.lower() for kw in ['input', 'output', 'constraint', 'limit', 'example']):
                        # 包含样例或重要信息，作为独立内容保存
                        problems.append({
                            "title": f"内容片段 (第{page_num}页)",
                            "content": content.strip(),
                            "pages": [page_num]
                        })
                        print(f"第{page_num}页作为独立片段保存")
                    else:
                        print(f"跳过第{page_num}页无标题且无关键内容")

        # 保存最后一个题目
        if current_problem and current_problem["content"]:
            print(f"保存最后一个题目: {current_problem['title']}, 页面: {current_problem['pages']}")
            problems.append({
                "title": current_problem["title"] or f"题目 {len(problems)+1}",
                "content": current_problem["content"].strip(),
                "pages": current_problem["pages"]
            })

        print(f"合并完成，总共 {len(problems)} 个题目")
        return problems
    
    def process_pdf(self, pdf_path: str, output_file: str = "competition_problems.md", output_dir: str = "题目", debug: bool = True) -> bool:
        """
        处理整个算法竞赛PDF文件
        
        Args:
            pdf_path: PDF文件路径
            output_file: 输出文件路径
            output_dir: 输出单独题目的目录
            debug: 是否开启调试模式，保存每页的原始输出
            
        Returns:
            bool: 处理是否成功
        """
        print(f"开始处理算法竞赛PDF: {pdf_path}")
        
        # 创建调试日志目录
        if debug:
            log_dir = "debug_logs"
            os.makedirs(log_dir, exist_ok=True)
            pdf_name = Path(pdf_path).stem
            debug_log_file = os.path.join(log_dir, f"{pdf_name}_debug.log")
            
            with open(debug_log_file, 'w', encoding='utf-8') as log_f:
                log_f.write(f"=== PDF处理调试日志 ===\n")
                log_f.write(f"PDF文件: {pdf_path}\n")
                log_f.write(f"处理时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_f.write(f"{'='*50}\n\n")
            
            print(f"调试模式开启，日志将保存到: {debug_log_file}")
        
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
                raw_contents.append(raw_content)
                print(f"第 {i+1} 页处理完成")
                
                # 调试日志：保存原始LLM输出
                if debug:
                    with open(debug_log_file, 'a', encoding='utf-8') as log_f:
                        log_f.write(f"=== 第 {i+1} 页 ===\n")
                        log_f.write(f"图片路径: {image_path}\n")
                        log_f.write(f"处理状态: 成功\n")
                        log_f.write(f"LLM输出长度: {len(raw_content)} 字符\n")
                        log_f.write(f"\n--- LLM输出 ---\n")
                        log_f.write(raw_content)
                        log_f.write(f"\n\n{'='*50}\n\n")
                        
            else:
                print(f"第 {i+1} 页处理失败")
                raw_contents.append("")
                
                # 调试日志：记录失败情况
                if debug:
                    with open(debug_log_file, 'a', encoding='utf-8') as log_f:
                        log_f.write(f"=== 第 {i+1} 页 ===\n")
                        log_f.write(f"图片路径: {image_path}\n")
                        log_f.write(f"处理状态: 失败\n")
                        log_f.write(f"错误信息: API请求失败或超时\n")
                        log_f.write(f"\n{'='*50}\n\n")
                
                # 如果失败，尝试重试一次
                if i > 0:
                    print(f"正在重试第 {i+1} 页...")
                    time.sleep(5)  # 等待一段时间后重试
                    raw_content = self.extract_content_from_image(image_path, i+1, len(image_paths))
                    if raw_content:
                        raw_contents[-1] = raw_content  # 更新内容
                        print(f"第 {i+1} 页重试成功")
                        
                        # 调试日志：记录重试成功
                        if debug:
                            with open(debug_log_file, 'a', encoding='utf-8') as log_f:
                                log_f.write(f"=== 第 {i+1} 页 (重试) ===\n")
                                log_f.write(f"图片路径: {image_path}\n")
                                log_f.write(f"处理状态: 重试成功\n")
                                log_f.write(f"LLM输出长度: {len(raw_content)} 字符\n")
                                log_f.write(f"\n--- LLM输出 (重试) ---\n")
                                log_f.write(raw_content)
                                log_f.write(f"\n\n{'='*50}\n\n")
            
            # 添加延迟避免API限制
            time.sleep(2)
        
        # 智能合并题目内容
        print("\n正在分析和合并内容...")
        
        # 先显示每页提取的内容概要
        for i, content in enumerate(raw_contents):
            if content.strip():
                has_problem = self.is_new_problem(content)
                has_sample = self.has_sample_data(content)
                is_likely_sample = self.is_likely_sample_page(content)
                print(f"第{i+1}页: 新题目={has_problem}, 样例={has_sample}, 可能样例页={is_likely_sample}, 长度={len(content)}")
                
                # 调试日志：记录分析结果
                if debug:
                    with open(debug_log_file, 'a', encoding='utf-8') as log_f:
                        log_f.write(f"=== 第 {i+1} 页分析结果 ===\n")
                        log_f.write(f"是否新题目: {has_problem}\n")
                        log_f.write(f"包含样例: {has_sample}\n")
                        log_f.write(f"可能是样例页: {is_likely_sample}\n")
                        log_f.write(f"内容长度: {len(content)}\n")
                        log_f.write(f"内容预览 (前200字符):\n{content[:200]}...\n")
                        log_f.write(f"\n{'='*30}\n\n")
            else:
                print(f"第{i+1}页: 空内容")
        
        problems = self.merge_problem_content(raw_contents)
        
        # 调试日志：记录合并结果
        if debug:
            with open(debug_log_file, 'a', encoding='utf-8') as log_f:
                log_f.write(f"=== 合并结果摘要 ===\n")
                log_f.write(f"总共提取题目数: {len(problems)}\n")
                for i, problem in enumerate(problems):
                    title = problem["title"] if problem["title"] else f"题目 {i+1}"
                    pages = ", ".join(map(str, problem["pages"]))
                    log_f.write(f"题目 {i+1}: {title} (页面: {pages})\n")
                log_f.write(f"\n{'='*50}\n\n")
        
        # 保存结果
        try:
            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                # 写入文档头部
                pdf_name = Path(pdf_path).stem
                f.write(f"# {pdf_name} - 竞赛题目\n\n")
                f.write(f"共处理 {len(image_paths)} 页，提取 {len(problems)} 道题目\n\n")
                f.write("---\n\n")
                
                # 写入每个题目
                for i, problem in enumerate(problems):
                    title = problem["title"] if problem["title"] else f"题目 {i+1}"
                    f.write(f"<!-- 题目 {i+1}, 来源页面: {', '.join(map(str, problem['pages']))} -->\n\n")
                    f.write(problem["content"])
                    f.write("\n\n---\n\n")
                    
                    # 提取题目名称，保存为单独文件
                    problem_title = title.replace("## ", "").replace("#", "").strip()
                    if "Problem" in problem_title:
                        # 规范化文件名
                        safe_title = re.sub(r'[^\w\s.-]', '_', problem_title)
                        safe_title = re.sub(r'\s+', '_', safe_title)
                        
                        # 写入单独题目文件
                        problem_file = os.path.join(output_dir, f"{safe_title}.md")
                        with open(problem_file, 'w', encoding='utf-8') as pf:
                            pf.write(f"# {problem_title}\n\n")
                            pf.write(problem["content"])
                            print(f"保存题目: {problem_file}")
                
            print(f"\n处理完成！竞赛题目已保存到: {output_file}")
            print(f"共处理 {len(image_paths)} 页，提取 {len(problems)} 道题目")
            if debug:
                print(f"调试日志已保存到: {debug_log_file}")
            
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
    parser.add_argument("--api-base", default="https://dashscope.aliyuncs.com/compatible-mode/v1", help="API基础URL")
    parser.add_argument("--model", default="qwen-vl-max", help="使用的模型")
    parser.add_argument("--output", default="extracted_content.md", help="输出文件路径")
    parser.add_argument("--output-dir", default="题目", help="输出单独题目的目录")
    parser.add_argument("--debug", action="store_true", help="开启调试模式，保存详细日志")
    parser.add_argument("--no-cache", action="store_true", help="禁用缓存功能")
    parser.add_argument("--clear-cache", action="store_true", help="清理缓存并退出")
    parser.add_argument("--cache-info", action="store_true", help="显示缓存信息并退出")
    
    args = parser.parse_args()
    
    # 创建pipeline用于缓存操作
    pipeline = PDFExtractionPipeline(
        api_key=args.api_key,
        api_base=args.api_base,
        model=args.model,
        use_cache=not args.no_cache
    )
    
    # 处理缓存管理命令
    if args.clear_cache:
        pipeline.clear_cache()
        return
        
    if args.cache_info:
        info = pipeline.get_cache_info()
        print(f"缓存信息:")
        print(f"  文件数量: {info['count']}")
        print(f"  总大小: {info['size'] / 1024 / 1024:.2f} MB")
        return
    
    # 检查文件是否存在
    if not os.path.exists(args.pdf_path):
        print(f"PDF文件不存在: {args.pdf_path}")
        return
    
    # 显示缓存状态
    if not args.no_cache:
        cache_info = pipeline.get_cache_info()
        print(f"缓存状态: {cache_info['count']} 个文件 ({cache_info['size'] / 1024 / 1024:.2f} MB)")
    
    success = pipeline.process_pdf(args.pdf_path, args.output, args.output_dir, args.debug)
    if success:
        print("处理成功完成！")
        if not args.no_cache:
            final_cache_info = pipeline.get_cache_info()
            print(f"最终缓存: {final_cache_info['count']} 个文件 ({final_cache_info['size'] / 1024 / 1024:.2f} MB)")
    else:
        print("处理过程中出现错误")

if __name__ == "__main__":
    main()
