#!/usr/bin/env python3
"""
PDF题目提取Pipeline (智能优化版)
主要使用LLM处理，但在样例部分提供原始文本参考
- 保持LLM处理以确保LaTeX格式正确
- 为样例部分提取原始文本作为参考
- 让LLM基于原始样例文本进行精确格式化
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
except ImportError as e:
    print(f"请安装必要的依赖: pip install pdf2image pillow requests pdfplumber")
    print(f"还需要安装poppler: ")
    print(f"  Ubuntu/Debian: sudo apt-get install poppler-utils")
    print(f"  macOS: brew install poppler")
    print(f"  Windows: 下载poppler二进制文件")
    exit(1)

class SmartPDFExtractionPipeline:
    def __init__(self, api_key: str, api_base: str = "https://api.openai.com/v1", model: str = "gpt-4-vision-preview", use_cache: bool = True):
        """
        初始化智能PDF提取pipeline
        
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
            "enhanced_with_text": 0,
            "pure_llm": 0,
            "cached_pages": 0,
            "total_pages": 0
        }

    def extract_sample_text_from_pdf(self, pdf_path: str) -> Dict[int, str]:
        """
        从PDF中提取样例相关的原始文本
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            Dict[int, str]: 页码 -> 该页的样例文本
        """
        sample_texts = {}
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    
                    if page_text and self.contains_sample_data(page_text):
                        # 提取样例相关的文本段落
                        sample_text = self.extract_sample_section(page_text)
                        if sample_text:
                            sample_texts[i + 1] = sample_text
                            print(f"第{i+1}页检测到样例数据，提取了{len(sample_text)}字符的参考文本")
                            
        except Exception as e:
            print(f"提取样例文本失败: {e}")
            
        return sample_texts

    def contains_sample_data(self, text: str) -> bool:
        """检测文本是否包含样例数据"""
        sample_indicators = [
            'Example',
            'Sample',
            'standard input',
            'standard output',
            'Input:',
            'Output:'
        ]
        
        text_lower = text.lower()
        for indicator in sample_indicators:
            if indicator.lower() in text_lower:
                return True
        return False

    def extract_sample_section(self, text: str) -> str:
        """提取样例相关的文本段落"""
        lines = text.split('\n')
        sample_lines = []
        in_sample_section = False
        
        for line in lines:
            line = line.strip()
            
            # 检测样例段落开始
            if re.search(r'(Example|Sample|standard\s+input|Input:|Output:)', line, re.IGNORECASE):
                in_sample_section = True
                sample_lines.append(line)
                continue
            
            # 检测样例段落结束
            if in_sample_section:
                # 如果遇到新的题目或章节，结束样例提取
                if re.search(r'(Problem\s+[A-Z]|Note|Input\s*$|Output\s*$|^[A-Z][a-z]+:)', line):
                    if not line.lower().startswith(('input', 'output')):
                        break
                
                sample_lines.append(line)
        
        return '\n'.join(sample_lines)

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

    def extract_content_from_image_enhanced(self, image_path: str, page_num: int, total_pages: int, sample_reference: Optional[str] = None) -> Optional[str]:
        """
        使用LLM从图片中提取内容，可选择提供样例参考文本
        
        Args:
            image_path: 图片路径
            page_num: 页码
            total_pages: 总页数
            sample_reference: 可选的样例参考文本
        """
        print(f"正在用LLM处理图片: {image_path} (第{page_num}/{total_pages}页)")
        if sample_reference:
            print(f"  >> 提供了{len(sample_reference)}字符的样例参考文本")
        
        # 首先尝试从缓存加载
        cache_key = f"{image_path}_{hashlib.md5((sample_reference or '').encode()).hexdigest()}"
        cached_content = self.load_from_cache(cache_key)
        if cached_content:
            print(f"第{page_num}页内容从缓存加载完成")
            self.stats["cached_pages"] += 1
            return cached_content
        
        # 编码图片  
        base64_image = self.encode_image_to_base64(image_path)
        
        # 构建增强的提示词
        if sample_reference:
            competition_prompt = f"""请仔细分析这张算法竞赛题目图片，精确提取所有内容。这是第{page_num}页(共{total_pages}页)。

**重要提示：我已经为你提供了本页的样例数据参考文本，请确保样例部分完全按照参考文本的数据内容！**

**样例参考文本：**
```
{sample_reference}
```

**处理要求：**
1. **新题目识别**: 
   - 仅当页面上有明显的题目开始标记(如"Problem X")时，才使用 ## Problem X. 题目名称 格式

2. **样例处理(极其重要)**:
   - 使用上面提供的样例参考文本中的精确数据
   - 将样例格式化为清晰的Input/Output结构
   - 样例数据必须与参考文本完全一致，不要修改任何数字或字符
   - 使用以下格式：
   ```
   **Input:**
   具体输入数据(与参考文本一致)

   **Output:**
   具体输出数据(与参考文本一致)
   ```

3. **数学公式**: 所有数学内容使用LaTeX格式，如 $n$、$10^9$、$$formula$$，不要使用\(\)

4. **完整提取**: 包括题目描述、限制条件、注释等所有内容

请直接输出markdown格式内容，确保样例数据与提供的参考文本完全一致！"""
            
            self.stats["enhanced_with_text"] += 1
        else:
            competition_prompt = f"""请仔细分析这张算法竞赛题目图片，精确提取所有内容。这是第{page_num}页(共{total_pages}页)。

**识别规则:**
1. **新题目识别**: 
   - 仅当页面上有明显的题目开始标记(如"Problem X")时，才使用 ## Problem X. 题目名称 格式

2. **样例格式**:
   - 样例数据必须完全按原始格式输出
   - 使用清晰的Input/Output结构：
   ```
   **Input:**
   具体输入数据

   **Output:**  
   具体输出数据
   ```

3. **数学公式**: 使用LaTeX格式 $formula$ 或 $$formula$$

4. **完整提取**: 不要遗漏任何内容

请直接输出markdown格式内容。"""
            
            self.stats["pure_llm"] += 1
        
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
                    print(f"第{page_num}页处理完成 ({len(content)} 字符)")
                    
                    # 保存到缓存
                    self.save_to_cache(cache_key, content)
                    
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

    def process_pdf_smart(self, pdf_path: str, output_file: str, debug: bool = False) -> bool:
        """
        智能PDF处理主函数
        主要使用LLM，但为样例提供原始文本参考
        """
        print(f"🚀 开始智能处理PDF: {pdf_path}")
        print("📝 策略: LLM主导 + 样例文本增强")
        print("=" * 60)
        
        # 重置统计
        self.stats = {k: 0 for k in self.stats}
        
        # 步骤1: 提取样例参考文本
        print("🔍 步骤1: 提取样例参考文本...")
        sample_references = self.extract_sample_text_from_pdf(pdf_path)
        
        if sample_references:
            print(f"✅ 在{len(sample_references)}页中发现样例数据")
            for page_num, ref_text in sample_references.items():
                print(f"  第{page_num}页: {len(ref_text)}字符的样例参考")
        else:
            print("ℹ️ 未发现明显的样例数据，将使用纯LLM模式")
        
        # 步骤2: 转换PDF为图片
        print("📸 步骤2: 转换PDF为图片...")
        image_paths = self.convert_pdf_to_images(pdf_path)
        
        if not image_paths:
            print("❌ PDF转换失败")
            return False
        
        self.stats["total_pages"] = len(image_paths)
        
        # 步骤3: 处理每页
        print("🧠 步骤3: 使用LLM处理每页...")
        all_contents = []
        
        debug_log_file = None
        if debug:
            debug_log_file = f"{os.path.splitext(pdf_path)[0]}_smart_debug.log"
            with open(debug_log_file, 'w', encoding='utf-8') as log_f:
                log_f.write(f"智能PDF处理调试日志\n")
                log_f.write(f"PDF文件: {pdf_path}\n")
                log_f.write(f"处理时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_f.write("=" * 80 + "\n\n")
        
        for i, image_path in enumerate(image_paths):
            page_num = i + 1
            
            # 获取该页的样例参考文本
            sample_ref = sample_references.get(page_num)
            
            # 处理页面
            content = self.extract_content_from_image_enhanced(
                image_path, page_num, len(image_paths), sample_ref
            )
            
            if content:
                all_contents.append(content)
                
                # 调试日志
                if debug and debug_log_file:
                    with open(debug_log_file, 'a', encoding='utf-8') as log_f:
                        log_f.write(f"=== 第 {page_num} 页 ===\n")
                        log_f.write(f"图片路径: {image_path}\n")
                        log_f.write(f"处理方式: {'样例增强' if sample_ref else '纯LLM'}\n")
                        log_f.write(f"输出长度: {len(content)} 字符\n")
                        
                        if sample_ref:
                            log_f.write(f"\n--- 样例参考文本 ---\n")
                            log_f.write(sample_ref)
                            log_f.write(f"\n")
                        
                        log_f.write(f"\n--- LLM输出 ---\n")
                        log_f.write(content)
                        log_f.write(f"\n\n{'='*50}\n\n")
                        
            else:
                print(f"⚠️ 第{page_num}页处理失败")
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
            print(f"  样例增强: {self.stats['enhanced_with_text']} 页")
            print(f"  纯LLM处理: {self.stats['pure_llm']} 页")
            print(f"  缓存命中: {self.stats['cached_pages']} 页")
            
            if debug and debug_log_file:
                print(f"  调试日志: {debug_log_file}")
            
            return True
            
        except Exception as e:
            print(f"❌ 保存文件失败: {e}")
            return False

    def merge_problem_content(self, contents: List[str], debug: bool = False) -> str:
        """合并问题内容"""
        if not contents:
            return ""
        
        # 导入原有的合并逻辑
        from pdf_extraction_pipeline import PDFExtractionPipeline
        
        dummy_pipeline = PDFExtractionPipeline("", "", "")
        return dummy_pipeline.merge_problem_content(contents, debug)

    def clear_cache(self):
        """清空缓存"""
        try:
            import shutil
            if os.path.exists(self.cache_dir):
                shutil.rmtree(self.cache_dir)
                os.makedirs(self.cache_dir, exist_ok=True)
                print("✅ 缓存已清空")
        except Exception as e:
            print(f"清空缓存失败: {e}")

    def get_cache_info(self) -> Dict[str, int]:
        """获取缓存信息"""
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

# 添加命令行接口
def main():
    parser = argparse.ArgumentParser(description='智能PDF算法竞赛题目提取工具')
    parser.add_argument('pdf_file', help='输入PDF文件路径')
    parser.add_argument('-o', '--output', default='extracted_content.md', help='输出markdown文件路径')
    parser.add_argument('-k', '--api-key', required=True, help='LLM API密钥')
    parser.add_argument('-b', '--api-base', default='https://dashscope.aliyuncs.com/compatible-mode/v1', help='API基础URL')
    parser.add_argument('-m', '--model', default='qwen-vl-max', help='使用的模型')
    parser.add_argument('--no-cache', action='store_true', help='禁用缓存')
    parser.add_argument('-d', '--debug', action='store_true', help='启用调试模式')
    parser.add_argument('--clear-cache', action='store_true', help='清空缓存')
    
    args = parser.parse_args()
    
    # 初始化智能pipeline
    pipeline = SmartPDFExtractionPipeline(
        api_key=args.api_key,
        api_base=args.api_base,
        model=args.model,
        use_cache=not args.no_cache
    )
    
    if args.clear_cache:
        pipeline.clear_cache()
        return True
    
    if not os.path.exists(args.pdf_file):
        print(f"❌ PDF文件不存在: {args.pdf_file}")
        return False
    
    # 处理PDF
    success = pipeline.process_pdf_smart(args.pdf_file, args.output, args.debug)
    
    if success:
        print("🎉 智能处理完成!")
        return True
    else:
        print("❌ 处理失败!")
        return False

if __name__ == "__main__":
    main()
