def remove_spaces_from_file(input_file_path, output_file_path):
    """
    读取一个文本文件，删除所有空格，并将结果保存到新文件中。

    参数:
    input_file_path (str): 输入文件的路径。
    output_file_path (str): 输出文件的路径。
    """
    try:
        # 以读取模式打开输入文件
        with open(input_file_path, 'r', encoding='utf-8') as reader:
            # 读取文件全部内容
            content = reader.read()

        # 使用 replace() 方法删除所有空格
        content_without_spaces = content.replace(' ', '')

        # 以写入模式打开输出文件
        with open(output_file_path, 'w', encoding='utf-8') as writer:
            # 将修改后的内容写入新文件
            writer.write(content_without_spaces)

        print(f"成功处理文件！已将 '{input_file_path}' 中删除空格后的内容保存到 '{output_file_path}'。")

    except FileNotFoundError:
        print(f"错误：找不到文件 '{input_file_path}'。请检查路径是否正确。")
    except Exception as e:
        print(f"处理文件时发生错误: {e}")

# --- 使用示例 ---
if __name__ == "__main__":
    # 定义你的输入文件名和希望的输出文件名
    input_file = '/home/chd/workplace/XW/rag/output_docx.txt'
    output_file = '/home/chd/workplace/XW/rag/modified.txt'
    # 调用函数来处理文件
    remove_spaces_from_file(input_file, output_file)

    # (可选) 打印出新文件的内容进行验证
    print("\n--- 新文件内容 ---")
    with open(output_file, 'r', encoding='utf-8') as f:
        print(f.read())
    print("--------------------")