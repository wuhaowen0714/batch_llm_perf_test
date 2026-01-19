import yaml
import csv
import os
import shutil
from evalscope.perf.main import run_perf_benchmark
from evalscope.perf.arguments import Arguments


def read_config(config_path):
    """读取配置文件"""
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    return config


def align_arrays(arrays_dict):
    """对齐数组长度
    
    Args:
        arrays_dict: 包含数组的字典，例如 {'number': [1,2,3], 'rate': 2}
    
    Returns:
        对齐后的字典，所有数组长度一致
    """
    # 将非数组转换为数组
    for key, value in arrays_dict.items():
        if not isinstance(value, list):
            arrays_dict[key] = [value]
    
    # 找出最大数组长度
    max_length = max(len(arr) for arr in arrays_dict.values())
    
    # 检查数组长度一致性并扩充
    for key, arr in arrays_dict.items():
        if len(arr) == 1:
            # 长度为1的数组扩充到最大长度
            arrays_dict[key] = arr * max_length
        elif len(arr) != max_length:
            # 长度不为1且不等于最大长度，报错
            raise ValueError(
                f"数组长度不一致: {key} 的长度为 {len(arr)}，期望为 1 或 {max_length}"
            )
    
    return arrays_dict


def extract_result_metrics(results):
    """从evalscope结果中提取指标
    
    Args:
        results: evalscope返回的结果
            - 旧版本 (0.17.0): 元组 (metrics_dict, percentiles_dict)
            - 新版本: 字典 {'parallel_X_number_Y': {'metrics': {...}, 'percentiles': {...}}}
    
    Returns:
        包含所需指标的字典
    """
    # 兼容两种格式
    if isinstance(results, tuple):
        # 旧版本格式: (metrics, percentiles)
        metrics, percentiles = results
    elif isinstance(results, dict):
        # 新版本格式: {'parallel_X_number_Y': {'metrics': {...}, 'percentiles': {...}}}
        # 获取第一个键对应的值
        first_key = next(iter(results))
        metrics = results[first_key]['metrics']
        percentiles = results[first_key]['percentiles']
    else:
        raise ValueError(f"不支持的结果格式: {type(results)}")
    
    # 找到90%对应的索引
    percentile_labels = percentiles['Percentiles']
    p90_index = percentile_labels.index('90%')
    
    extracted = {
        'ttft': metrics['Average time to first token (s)'],
        'p90_ttft': percentiles['TTFT (s)'][p90_index],
        'tpot': metrics['Average time per output token (s)'],
        'p90_tpot': percentiles['TPOT (s)'][p90_index],
        'input_token_throughput': (
            metrics['Total token throughput (tok/s)'] - 
            metrics['Output token throughput (tok/s)']
        ),
        'output_token_throughput': metrics['Output token throughput (tok/s)']
    }
    
    return extracted


def run_single_test(model_config, test_params):
    """运行单次测试
    
    Args:
        model_config: 模型配置字典
        test_params: 测试参数字典
    
    Returns:
        evalscope的测试结果
    """
    task_cfg = Arguments(
        # 模型配置
        model=model_config['model'],
        url=model_config['url'],
        api=model_config['api'],
        api_key=model_config['api_key'],
        tokenizer_path=model_config['tokenizer_path'],
        
        # 测试参数
        number=[test_params['number']],
        parallel=[test_params['concurrency']],
        rate=test_params['rate'],
        
        # 输入输出长度参数
        min_prompt_length=test_params['min_prompt_length'] - test_params['prefix_length'],
        max_prompt_length=test_params['max_prompt_length'] - test_params['prefix_length'],
        min_tokens=test_params['min_tokens'],
        max_tokens=test_params['max_tokens'],
        prefix_length=test_params['prefix_length'],
        
        # 其他配置
        dataset='random',
        log_every_n_query=200000,
        extra_args={'ignore_eos': True}
    )
    
    results = run_perf_benchmark(task_cfg)
    return results


def clean_outputs_folder(outputs_dir='outputs'):
    """清理evalscope生成的outputs文件夹
    
    Args:
        outputs_dir: outputs文件夹路径，默认为'outputs'
    """
    if os.path.exists(outputs_dir):
        try:
            shutil.rmtree(outputs_dir)
            print(f"  已清理 {outputs_dir} 文件夹")
        except Exception as e:
            print(f"  警告: 清理 {outputs_dir} 失败: {e}")


def get_fieldnames_by_mode(mode):
    """根据mode获取对应的CSV字段名
    
    Args:
        mode: 测试模式 ('all', 'prefill', 'decode')
    
    Returns:
        字段名列表
    """
    if mode == 'prefill':
        return ['input_tokens', 'output_tokens', 'concurrency', 'number', 'ttft', 'p90_ttft', 'input_token_throughput']
    elif mode == 'decode':
        return ['input_tokens', 'prefix_length', 'output_tokens', 'concurrency', 'number', 'tpot', 'p90_tpot', 
                'output_token_throughput']
    else:  # 'all' 或默认
        return [
            'input_tokens', 'prefix_length', 'output_tokens', 
            'rate', 'concurrency', 'number',
            'ttft', 'p90_ttft', 'tpot', 'p90_tpot',
            'input_token_throughput', 'output_token_throughput'
        ]


def write_to_csv(output_file, test_params, metrics, is_new_file, mode='all'):
    """将测试结果写入CSV文件
    
    Args:
        output_file: 输出文件路径
        test_params: 测试参数字典
        metrics: 提取的指标字典
        is_new_file: 是否是新文件（需要写表头）
        mode: 测试模式 ('all', 'prefill', 'decode')
    """
    fieldnames = get_fieldnames_by_mode(mode)
    
    # 构建完整的数据行
    full_row = {
        'input_tokens': test_params['input_tokens'],
        'prefix_length': test_params['prefix_length'],
        'output_tokens': test_params['output_tokens'],
        'rate': test_params['rate'],
        'concurrency': test_params['concurrency'],
        'number': test_params['number'],
        **metrics
    }
    
    # 只保留当前mode需要的字段
    row = {k: full_row[k] for k in fieldnames}
    
    file_mode = 'w' if is_new_file else 'a'
    with open(output_file, file_mode, newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if is_new_file:
            writer.writeheader()
        writer.writerow(row)


def run_auto_test(config_path):
    """运行自动化测试主函数
    
    Args:
        config_path: 配置文件路径
    """
    # 读取配置
    config = read_config(config_path)
    
    output_file = config['output_file']
    model_config = config['model_config']
    eval_config = config['eval_config']
    test_mode = config.get('mode', 'all')  # 默认为 'all' 模式
    
    print(f"测试模式: {test_mode}")
    
    # 检查输出文件是否存在
    is_new_file = not os.path.exists(output_file)
    
    # 对齐eval_config中的数组
    # 第一组：number, concurrency, rate
    group1 = {
        'number': eval_config['number'],
        'concurrency': eval_config['concurrency'],
        'rate': eval_config['rate']
    }
    group1_aligned = align_arrays(group1)
    
    # 第二组：input_tokens, output_tokens, prefix_length
    group2 = {
        'input_tokens': eval_config['input_tokens'],
        'output_tokens': eval_config['output_tokens'],
        'prefix_length': eval_config['prefix_length']
    }
    group2_aligned = align_arrays(group2)
    
    # 计算总测试数量
    total_tests = len(group1_aligned['number']) * len(group2_aligned['input_tokens'])
    print(f"总共需要运行 {total_tests} 组测试")
    
    test_count = 0
    
    # 遍历所有测试组合
    for i in range(len(group2_aligned['input_tokens'])):
        input_tokens = group2_aligned['input_tokens'][i]
        output_tokens = group2_aligned['output_tokens'][i]
        prefix_length = group2_aligned['prefix_length'][i]
        
        for j in range(len(group1_aligned['number'])):
            number = group1_aligned['number'][j]
            concurrency = group1_aligned['concurrency'][j]
            rate = group1_aligned['rate'][j]
            
            test_count += 1
            print(f"\n[{test_count}/{total_tests}] 运行测试:")
            print(f"  input_tokens={input_tokens}, output_tokens={output_tokens}, "
                  f"prefix_length={prefix_length}")
            print(f"  number={number}, concurrency={concurrency}, rate={rate}")
            
            # 构建测试参数
            test_params = {
                'number': number,
                'concurrency': concurrency,
                'rate': rate,
                'min_prompt_length': input_tokens,
                'max_prompt_length': input_tokens,
                'min_tokens': output_tokens,
                'max_tokens': output_tokens,
                'prefix_length': prefix_length,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens
            }
            
            try:
                # 运行测试
                results = run_single_test(model_config, test_params)
                
                # 提取指标
                metrics = extract_result_metrics(results)
                
                # 写入CSV
                write_to_csv(output_file, test_params, metrics, is_new_file, test_mode)
                is_new_file = False  # 第一次写入后，后续都是追加
                
                print(f"  ✓ 测试完成，结果已写入 {output_file}")
                print(f"    TTFT: {metrics['ttft']:.4f}s, "
                      f"TPOT: {metrics['tpot']:.4f}s, "
                      f"Output throughput: {metrics['output_token_throughput']:.2f} tok/s")
                
            except Exception as e:
                print(f"  ✗ 测试失败: {str(e)}")
                # 继续执行下一个测试
            finally:
                # 清理evalscope生成的outputs文件夹
                clean_outputs_folder()
    
    print(f"\n所有测试完成！结果已保存到 {output_file}")


if __name__ == "__main__":
    ## config 为输入参数
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default="config.yaml", help="配置文件路径")
    args = parser.parse_args()
    config_path = args.config
    run_auto_test(config_path)
