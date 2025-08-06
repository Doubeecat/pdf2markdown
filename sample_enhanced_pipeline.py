#!/usr/bin/env python3
"""
PDF处理工具 - 样例数据优化版
专门解决样例格式问题：
1. 主要使用LLM保证LaTeX格式
2. 对检测到样例的页面，提供额外的原始文本参考
3. 使用更精确的样例格式化提示
"""

import os
import json
import time
import requests
from typing import Optional
from pdf_extraction_pipeline import PDFExtractionPipeline

class SampleEnhancedPipeline(PDFExtractionPipeline):
    def __init__(self, api_key: str, api_base: str, model: str, use_cache: bool = True):
        super().__init__(api_key, api_base, model, use_cache)
        
    def extract_content_from_image(self, image_path: str, page_num: int, total_pages: int) -> Optional[str]:
        """
        增强版内容提取，针对样例页面使用特殊提示
        """
        print(f"正在处理图片: {image_path} (第{page_num}/{total_pages}页)")
        
        # 首先尝试从缓存加载
        cached_content = self.load_from_cache(image_path)
        if cached_content:
            print(f"第{page_num}页内容从缓存加载完成 ({len(cached_content)} 字符)")
            return cached_content
        
        # 编码图片  
        base64_image = self.encode_image_to_base64(image_path)
        
        # 针对算法竞赛题目的超级优化提示词（特别关注样例）
        competition_prompt = f"""请仔细分析这张算法竞赛题目图片，精确提取所有内容。这是第{page_num}页(共{total_pages}页)。

**样例格式化的重要规则（请严格遵循）：**

1. **新题目识别**: 
   - 仅当页面上有明显的题目开始标记(如"Problem X")时，才使用 ## Problem X. 题目名称 格式

2. **样例处理（极其重要）**:
   - 当你看到"Example"或类似的样例标题时，请按以下格式输出：
   
   ### Example
   
   **Input:**
   ```
   [第一行输入]
   [第二行输入]
   [第三行输入]
   ...
   ```
   
   **Output:**
   ```
   [第一行输出]
   [第二行输出]
   [第三行输出]
   ...
   ```
   
   - 关键原则：
     * 仔细观察图片中的数据对齐和分行
     * 每行数据独立一行，不要合并
     * 输入和输出要清楚分开
     * 数字和空格的排列要保持原样
     * 如果有表格形式的数据，按行提取

3. **数学公式**: 使用LaTeX格式 $formula$ 或 $$formula$$

4. **其他格式**:
   - 文件信息用**加粗**：**Input file: standard input**
   - 限制信息用**加粗**：**Time limit: 1 second**

5. **完整提取**: 不要遗漏任何内容，包括Note部分

**特别注意样例数据的精确性 - 这是评判质量的关键！**

请直接输出markdown格式内容。"""
        
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
                print(f"请求发送失败: {e}")
                if attempt < max_retries - 1:
                    print(f"{retry_delay}秒后重试...")
                    time.sleep(retry_delay)
                else:
                    return None
        
        return None

def main():
    """测试样例优化版本"""
    import json
    
    # 读取配置
    with open('config.json') as f:
        config = json.load(f)
        api_config = config['api_settings']['qwen']
    
    # 初始化管道
    pipeline = SampleEnhancedPipeline(
        api_key=api_config['api_key'],
        api_base=api_config['api_base'],
        model=api_config['model']
    )
    
    print("🚀 样例优化版PDF处理")
    print("=" * 50)
    
    # 处理PDF
    success = pipeline.process_pdf('2025牛客多校7_zh.pdf', '完整题目_样例优化.md', debug=True)
    
    if success:
        print("🎉 处理完成!")
        print("📄 输出文件: 完整题目_样例优化.md")
        print("🔍 调试日志: 2025牛客多校7_zh_debug.log")
    else:
        print("❌ 处理失败")

if __name__ == "__main__":
    main()
