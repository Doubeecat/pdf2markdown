#!/usr/bin/env python3
"""
算法竞赛题目处理工具集
提供批处理、验证、格式化等功能
"""

import os
import re
import json
from pathlib import Path
from typing import List, Dict, Tuple
import argparse

class CompetitionProblemProcessor:
    """算法竞赛题目处理器"""
    
    def __init__(self):
        self.problem_pattern = re.compile(r'## Problem ([A-Z])\. (.+)')
        self.time_limit_pattern = re.compile(r'Time limit: (.+)')
        self.memory_limit_pattern = re.compile(r'Memory limit: (.+)')
        
    def extract_problems(self, markdown_file: str) -> List[Dict]:
        """
        从markdown文件中提取单个题目
        
        Args:
            markdown_file: markdown文件路径
            
        Returns:
            List[Dict]: 题目列表
        """
        with open(markdown_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        problems = []
        sections = content.split('---')
        
        for section in sections:
            section = section.strip()
            if not section or section.startswith('#'):
                continue
                
            problem_match = self.problem_pattern.search(section)
            if problem_match:
                problem_id = problem_match.group(1)
                problem_title = problem_match.group(2).strip()
                
                # 提取时间和内存限制
                time_match = self.time_limit_pattern.search(section)
                memory_match = self.memory_limit_pattern.search(section)
                
                problem_data = {
                    'id': problem_id,
                    'title': problem_title,
                    'time_limit': time_match.group(1) if time_match else 'Unknown',
                    'memory_limit': memory_match.group(1) if memory_match else 'Unknown',
                    'content': section
                }
                
                problems.append(problem_data)
        
        return problems
    
    def split_problems_to_files(self, markdown_file: str, output_dir: str = "problems"):
        """
        将题目分割为单独的文件
        
        Args:
            markdown_file: 输入的markdown文件
            output_dir: 输出目录
        """
        problems = self.extract_problems(markdown_file)
        
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        print(f"共提取到 {len(problems)} 个题目")
        
        for problem in problems:
            filename = f"Problem_{problem['id']}_{self.sanitize_filename(problem['title'])}.md"
            filepath = output_path / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# Problem {problem['id']}. {problem['title']}\n\n")
                f.write(f"**Time Limit:** {problem['time_limit']}\n")
                f.write(f"**Memory Limit:** {problem['memory_limit']}\n\n")
                f.write("---\n\n")
                f.write(problem['content'])
            
            print(f"保存题目: {filename}")
    
    def sanitize_filename(self, filename: str) -> str:
        """清理文件名中的特殊字符"""
        # 移除或替换不合法的文件名字符
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        filename = filename.replace(' ', '_')
        return filename[:50]  # 限制长度
    
    def validate_latex(self, content: str) -> List[str]:
        """
        验证LaTeX公式的语法
        
        Args:
            content: 文档内容
            
        Returns:
            List[str]: 错误列表
        """
        errors = []
        
        # 检查未闭合的$符号
        inline_count = content.count('$')
        if inline_count % 2 != 0:
            errors.append("发现未配对的行内公式符号 $")
        
        # 检查未闭合的$$符号
        display_matches = re.findall(r'\$\$', content)
        if len(display_matches) % 2 != 0:
            errors.append("发现未配对的独立公式符号 $$")
        
        # 检查常见的LaTeX错误
        common_errors = [
            (r'\\frac\{[^}]*\}\{[^}]*\}', "分数格式"),
            (r'\\sum_\{[^}]*\}', "求和符号"),
            (r'\\prod_\{[^}]*\}', "乘积符号"),
        ]
        
        for pattern, desc in common_errors:
            if re.search(pattern, content):
                # 这里可以添加更复杂的验证逻辑
                pass
        
        return errors
    
    def generate_problem_index(self, problems_dir: str, output_file: str = "index.md"):
        """
        生成题目索引
        
        Args:
            problems_dir: 题目目录
            output_file: 索引文件名
        """
        problems_path = Path(problems_dir)
        
        if not problems_path.exists():
            print(f"题目目录不存在: {problems_dir}")
            return
        
        problem_files = list(problems_path.glob("Problem_*.md"))
        problem_files.sort()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# 算法竞赛题目索引\n\n")
            f.write("## 题目列表\n\n")
            
            for problem_file in problem_files:
                # 从文件名解析题目信息
                filename = problem_file.stem
                parts = filename.split('_', 2)
                if len(parts) >= 2:
                    problem_id = parts[1]
                    problem_title = parts[2].replace('_', ' ') if len(parts) > 2 else "Unknown"
                    
                    f.write(f"- [Problem {problem_id}. {problem_title}]({problem_file.name})\n")
        
        print(f"生成索引文件: {output_file}")

class CompetitionBatchProcessor:
    """批处理多个竞赛PDF"""
    
    def __init__(self, api_key: str, api_base: str = "https://api.openai.com/v1", model: str = "gpt-4-vision-preview"):
        from pdf_extraction_pipeline import PDFExtractionPipeline
        self.pipeline = PDFExtractionPipeline(api_key, api_base, model)
        self.processor = CompetitionProblemProcessor()
    
    def process_directory(self, pdf_dir: str, output_dir: str = "contests"):
        """
        批处理目录中的所有PDF文件
        
        Args:
            pdf_dir: PDF文件目录
            output_dir: 输出目录
        """
        pdf_path = Path(pdf_dir)
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        pdf_files = list(pdf_path.glob("*.pdf"))
        
        if not pdf_files:
            print(f"在 {pdf_dir} 中未找到PDF文件")
            return
        
        print(f"找到 {len(pdf_files)} 个PDF文件")
        
        for pdf_file in pdf_files:
            print(f"\n{'='*50}")
            print(f"处理文件: {pdf_file.name}")
            print(f"{'='*50}")
            
            # 为每个PDF创建单独的输出目录
            contest_name = pdf_file.stem
            contest_dir = output_path / contest_name
            contest_dir.mkdir(exist_ok=True)
            
            # 处理PDF
            markdown_file = contest_dir / f"{contest_name}.md"
            success = self.pipeline.process_pdf(str(pdf_file), str(markdown_file))
            
            if success:
                # 分割题目到单独文件
                problems_dir = contest_dir / "problems"
                self.processor.split_problems_to_files(str(markdown_file), str(problems_dir))
                
                # 生成索引
                index_file = contest_dir / "index.md"
                self.processor.generate_problem_index(str(problems_dir), str(index_file))
                
                print(f"✅ 成功处理: {pdf_file.name}")
            else:
                print(f"❌ 处理失败: {pdf_file.name}")

def main():
    parser = argparse.ArgumentParser(description="算法竞赛题目处理工具")
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 单文件处理
    single_parser = subparsers.add_parser('single', help='处理单个PDF文件')
    single_parser.add_argument('pdf_file', help='PDF文件路径')
    single_parser.add_argument('--api-key', required=True, help='API密钥')
    single_parser.add_argument('--api-base', default='https://api.openai.com/v1', help='API基础URL')
    single_parser.add_argument('--model', default='gpt-4-vision-preview', help='模型名称')
    single_parser.add_argument('--output', help='输出文件路径')
    
    # 批处理
    batch_parser = subparsers.add_parser('batch', help='批处理多个PDF文件')
    batch_parser.add_argument('pdf_dir', help='PDF文件目录')
    batch_parser.add_argument('--api-key', required=True, help='API密钥')
    batch_parser.add_argument('--api-base', default='https://api.openai.com/v1', help='API基础URL')
    batch_parser.add_argument('--model', default='gpt-4-vision-preview', help='模型名称')
    batch_parser.add_argument('--output', default='contests', help='输出目录')
    
    # 题目分割
    split_parser = subparsers.add_parser('split', help='分割题目到单独文件')
    split_parser.add_argument('markdown_file', help='markdown文件路径')
    split_parser.add_argument('--output', default='problems', help='输出目录')
    
    # 生成索引
    index_parser = subparsers.add_parser('index', help='生成题目索引')
    index_parser.add_argument('problems_dir', help='题目目录')
    index_parser.add_argument('--output', default='index.md', help='索引文件名')
    
    args = parser.parse_args()
    
    if args.command == 'single':
        from pdf_extraction_pipeline import PDFExtractionPipeline
        pipeline = PDFExtractionPipeline(args.api_key, args.api_base, args.model)
        
        output_file = args.output or f"{Path(args.pdf_file).stem}_problems.md"
        success = pipeline.process_pdf(args.pdf_file, output_file)
        
        if success:
            # 自动分割题目
            processor = CompetitionProblemProcessor()
            problems_dir = Path(args.pdf_file).stem + "_problems"
            processor.split_problems_to_files(output_file, problems_dir)
            processor.generate_problem_index(problems_dir)
    
    elif args.command == 'batch':
        batch_processor = CompetitionBatchProcessor(args.api_key, args.api_base, args.model)
        batch_processor.process_directory(args.pdf_dir, args.output)
    
    elif args.command == 'split':
        processor = CompetitionProblemProcessor()
        processor.split_problems_to_files(args.markdown_file, args.output)
    
    elif args.command == 'index':
        processor = CompetitionProblemProcessor()
        processor.generate_problem_index(args.problems_dir, args.output)
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()

# 使用示例
"""
# 处理单个竞赛PDF
python competition_tools.py single contest.pdf --api-key YOUR_API_KEY

# 批处理多个竞赛PDF
python competition_tools.py batch ./pdfs --api-key YOUR_API_KEY --output ./contests

# 分割已有的markdown文件
python competition_tools.py split contest_problems.md --output ./problems

# 生成题目索引
python competition_tools.py index ./problems --output index.md
"""