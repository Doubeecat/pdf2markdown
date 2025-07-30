#!/usr/bin/env python3
"""
牛客暑期多校训练营PDF处理示例
展示如何处理你提供的竞赛PDF文件
"""

import os
import sys
from pathlib import Path

# 假设你已经有了这些模块
from pdf_extraction_pipeline import PDFExtractionPipeline
from cp_tools import CompetitionProblemProcessor, CompetitionBatchProcessor

def load_config():
    """加载配置文件，如果不存在则创建默认配置"""
    config_file = "config.json"
    
    # 默认配置
    default_config = {
        "api_settings": {
            "openai": {
                "api_key": "sk-your-openai-key-here",
                "api_base": "https://api.openai.com/v1", 
                "model": "gpt-4-vision-preview"
            },
            "claude": {
                "api_key": "claude-your-key-here",
                "api_base": "https://api.anthropic.com/v1",
                "model": "claude-3-sonnet-20240229"
            },
            "qwen": {
                "api_key": "sk-your-qwen-key",
                "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model": "qwen-vl-plus"
            }
        },
        "processing_settings": {
            "default_api": "claude",
            "pdf_file": "example.pdf",
            "output_file": "problems.md",
            "problems_dir": "problems",
            "index_file": "index.md",
            "dpi": 400,
            "delay_between_pages": 2,
            "max_tokens": 3000,
            "auto_split": True,
            "generate_index": True,
            "validate_latex": True
        },
        "batch_settings": {
            "pdf_directory": "./contest_pdfs",
            "output_directory": "./processed_contests"
        }
    }
    
    # 检查配置文件是否存在
    if not os.path.exists(config_file):
        print(f"⚠️  配置文件 {config_file} 不存在，正在创建默认配置...")
        
        # 创建默认配置文件
        import json
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        
        print(f"✅ 已创建默认配置文件: {config_file}")
        print(f"📝 请编辑 {config_file} 填入你的API密钥")
        
        # 提示用户需要配置API密钥
        print("\n⚠️  注意: 请在配置文件中设置正确的API密钥后重新运行程序")
        return None
    
    # 读取配置文件
    try:
        import json
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        print(f"✅ 成功加载配置文件: {config_file}")
        return config
        
    except Exception as e:
        print(f"❌ 读取配置文件失败: {e}")
        print(f"请检查 {config_file} 的格式是否正确")
        return None

def validate_api_config(config, api_name):
    """验证API配置是否有效"""
    if api_name not in config["api_settings"]:
        print(f"❌ 配置文件中未找到 {api_name} API配置")
        return False
    
    api_config = config["api_settings"][api_name]
    
    # 检查必需的字段
    required_fields = ["api_key", "api_base", "model"]
    for field in required_fields:
        if field not in api_config:
            print(f"❌ {api_name} API配置缺少字段: {field}")
            return False
        
        # 检查是否为默认占位符
        if "your-" in api_config[field] or "key-here" in api_config[field]:
            print(f"❌ 请在配置文件中设置正确的 {api_name} {field}")
            return False
    
    return True

def process_contest():
    
    # 加载配置
    config = load_config()
    if config is None:
        return False
    
    # 获取API设置
    processing_settings = config["processing_settings"]
    api_name = processing_settings.get("default_api", "claude")
    
    # 验证API配置
    if not validate_api_config(config, api_name):
        return False
    
    api_config = config["api_settings"][api_name]
    
    print(f"🚀 使用 {api_name.upper()} API 处理PDF")
    print("="*60)
    
    # 初始化pipeline
    pipeline = PDFExtractionPipeline(
        api_key=api_config["api_key"],
        api_base=api_config["api_base"], 
        model=api_config["model"]
    )
    
    # PDF文件路径（你的文件）
    pdf_file = "example.pdf"
    
    if not os.path.exists(pdf_file):
        print(f"❌ PDF文件不存在: {pdf_file}")
        print("请确保PDF文件在当前目录下")
        return False
    
    print(f"📄 处理文件: {pdf_file}")
    
    # 步骤1: 提取完整题目到markdown
    output_file = "完整题目.md"
    print(f"\n📝 步骤1: 提取题目到 {output_file}")
    
    success = pipeline.process_pdf(pdf_file, output_file)
    
    if not success:
        print("❌ PDF处理失败")
        return False
    
    print("✅ PDF处理完成!")
    
    # 步骤2: 分割单个题目
    print(f"\n🔧 步骤2: 分割题目到单独文件")
    
    processor = CompetitionProblemProcessor()
    problems_dir = "题目"
    
    # 分割题目
    processor.split_problems_to_files(output_file, problems_dir)
    
    # 生成索引
    index_file = "索引.md" 
    processor.generate_problem_index(problems_dir, index_file)
    
    print(f"✅ 题目分割完成! 输出目录: {problems_dir}")
    print(f"📋 索引文件: {index_file}")
    
    # 步骤3: 验证LaTeX公式
    print(f"\n🔍 步骤3: 验证LaTeX公式")
    
    with open(output_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    errors = processor.validate_latex(content)
    if errors:
        print("⚠️  发现LaTeX语法问题:")
        for error in errors:
            print(f"   - {error}")
    else:
        print("✅ LaTeX语法检查通过")
    
    # 步骤4: 生成统计信息
    print(f"\n📊 步骤4: 生成统计信息")
    generate_contest_stats(problems_dir)
    
    print(f"\n🎉 处理完成!")
    print(f"📁 输出文件:")
    print(f"   - 完整题目: {output_file}")
    print(f"   - 分割题目: {problems_dir}/")
    print(f"   - 题目索引: {index_file}")
    
    return True

def generate_contest_stats(problems_dir: str):
    """生成竞赛统计信息"""
    problems_path = Path(problems_dir)
    
    if not problems_path.exists():
        print(f"题目目录不存在: {problems_dir}")
        return
    
    problem_files = list(problems_path.glob("Problem_*.md"))
    
    stats = {
        "total_problems": len(problem_files),
        "time_limits": {},
        "memory_limits": {}
    }
    
    for problem_file in problem_files:
        try:
            with open(problem_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 提取时间限制
            import re
            time_match = re.search(r'\*\*Time Limit:\*\* (.+)', content)
            if time_match:
                time_limit = time_match.group(1)
                stats["time_limits"][time_limit] = stats["time_limits"].get(time_limit, 0) + 1
            
            # 提取内存限制  
            memory_match = re.search(r'\*\*Memory Limit:\*\* (.+)', content)
            if memory_match:
                memory_limit = memory_match.group(1)
                stats["memory_limits"][memory_limit] = stats["memory_limits"].get(memory_limit, 0) + 1
                
        except Exception as e:
            print(f"处理文件 {problem_file} 时出错: {e}")
    
    # 输出统计信息
    print(f"📈 竞赛统计:")
    print(f"   - 总题目数: {stats['total_problems']}")
    print(f"   - 时间限制分布: {stats['time_limits']}")
    print(f"   - 内存限制分布: {stats['memory_limits']}")

def batch_process_contests():
    
    print("🔄 批量处理模式")
    print("="*50)
    
    # 加载配置
    config = load_config()
    if config is None:
        return False
    
    # 获取批处理设置
    batch_settings = config["batch_settings"]
    processing_settings = config["processing_settings"]
    api_name = processing_settings.get("default_api", "claude")
    
    # 验证API配置
    if not validate_api_config(config, api_name):
        return False
    
    api_config = config["api_settings"][api_name]
    
    # 获取目录配置
    pdf_directory = batch_settings.get("pdf_directory", "./contest_pdfs")
    output_directory = batch_settings.get("output_directory", "./processed_contests")
    
    # 检查目录
    if not os.path.exists(pdf_directory):
        print(f"❌ PDF目录不存在: {pdf_directory}")
        print("请创建目录并放入PDF文件，或在config.json中修改pdf_directory路径")
        return False
    
    print(f"📂 PDF目录: {pdf_directory}")
    print(f"📂 输出目录: {output_directory}")
    print(f"🤖 使用API: {api_name.upper()}")
    
    # 初始化批处理器
    batch_processor = CompetitionBatchProcessor(
        api_key=api_config["api_key"],
        api_base=api_config["api_base"],
        model=api_config["model"]
    )
    
    # 开始批处理
    batch_processor.process_directory(pdf_directory, output_directory)
    
    print("🎉 批量处理完成!")
    return True

def create_sample_structure():
    """创建示例目录结构"""
    
    print("📁 创建示例目录结构...")
    
    # 加载配置以获取目录设置
    config = load_config()
    if config is None:
        # 如果配置文件刚创建，使用默认值
        directories = [
            "contest_pdfs",
            "processed_contests", 
            "cache",
            "outputs"
        ]
    else:
        # 从配置获取目录
        batch_settings = config.get("batch_settings", {})
        pdf_dir = batch_settings.get("pdf_directory", "./contest_pdfs")
        output_dir = batch_settings.get("output_directory", "./processed_contests")
        
        directories = [
            pdf_dir.lstrip("./"),
            output_dir.lstrip("./"),
            "cache",
            "outputs"
        ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"   ✅ 创建目录: {directory}")
    
    print("   ✅ 目录结构创建完成")

def show_config_info():
    """显示当前配置信息"""
    
    config = load_config()
    if config is None:
        return
    
    print("\n📋 当前配置信息:")
    print("="*50)
    
    # 显示API设置
    processing_settings = config.get("processing_settings", {})
    default_api = processing_settings.get("default_api", "claude")
    
    print(f"🤖 默认API: {default_api.upper()}")
    
    api_settings = config.get("api_settings", {})
    if default_api in api_settings:
        api_config = api_settings[default_api]
        print(f"   - 模型: {api_config.get('model', 'Unknown')}")
        print(f"   - API Base: {api_config.get('api_base', 'Unknown')}")
        
        # 检查API密钥是否已设置
        api_key = api_config.get('api_key', '')
        if "your-" in api_key or "key-here" in api_key:
            print(f"   - API密钥: ❌ 未设置")
        else:
            print(f"   - API密钥: ✅ 已设置")
    
    # 显示文件设置
    print(f"\n📁 文件设置:")
    print(f"   - PDF文件: {processing_settings.get('pdf_file', 'example.pdf')}")
    print(f"   - 输出文件: {processing_settings.get('output_file', 'problems.md')}")
    print(f"   - 题目目录: {processing_settings.get('problems_dir', 'problems')}")
    print(f"   - 索引文件: {processing_settings.get('index_file', 'index.md')}")
    
    # 显示处理设置
    print(f"\n⚙️  处理设置:")
    print(f"   - DPI: {processing_settings.get('dpi', 400)}")
    print(f"   - 页面延迟: {processing_settings.get('delay_between_pages', 2)}秒")
    print(f"   - 最大Token: {processing_settings.get('max_tokens', 3000)}")
    print(f"   - 自动分割: {'✅' if processing_settings.get('auto_split', True) else '❌'}")
    print(f"   - 生成索引: {'✅' if processing_settings.get('generate_index', True) else '❌'}")
    print(f"   - LaTeX验证: {'✅' if processing_settings.get('validate_latex', True) else '❌'}")
    
    # 显示批处理设置
    batch_settings = config.get("batch_settings", {})
    print(f"\n🔄 批处理设置:")
    print(f"   - PDF目录: {batch_settings.get('pdf_directory', './contest_pdfs')}")
    print(f"   - 输出目录: {batch_settings.get('output_directory', './processed_contests')}")


if __name__ == "__main__":
    print("🏆 牛客算法竞赛PDF处理工具")
    print("="*50)
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "single":
            # 处理单个PDF
            process_contest()
        elif command == "batch":
            # 批量处理
            batch_process_contests()  
        elif command == "setup":
            # 创建目录结构
            create_sample_structure()
        else:
            print("❌ 未知命令")
            print("可用命令: single, batch, setup")
    else:
        print("使用方法:")
        print("  python nowcoder_example.py single   # 处理单个PDF")
        print("  python nowcoder_example.py batch    # 批量处理")
        print("  python nowcoder_example.py setup    # 创建目录结构")

# 期望的输出结构示例