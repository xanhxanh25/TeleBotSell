import os

def merge_python_files(output_filename="fullcode.txt"):
    # Các thư mục muốn bỏ qua để tránh file output quá nặng hoặc chứa code rác
    exclude_dirs = {'.venv', '__pycache__', '.git', 'logs', '.idea', '.vscode'}
    
    # Lấy đường dẫn thư mục hiện tại (nơi đặt script này)
    current_dir = os.getcwd()
    
    with open(output_filename, "w", encoding="utf-8") as outfile:
        for root, dirs, files in os.walk(current_dir):
            # Loại bỏ các thư mục không mong muốn khỏi danh sách quét
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                # Chỉ lấy các file có đuôi .py và không phải chính file script này
                if file.endswith(".py") and file != os.path.basename(__file__):
                    file_path = os.path.join(root, file)
                    
                    # Tính toán đường dẫn tương đối để ghi vào tiêu đề file cho đẹp
                    relative_path = os.path.relpath(file_path, current_dir)
                    
                    # Ghi tiêu đề phân cách giữa các file
                    outfile.write(f"\n{'='*80}\n")
                    outfile.write(f" FILE: {relative_path}\n")
                    outfile.write(f"{'='*80}\n\n")
                    
                    try:
                        with open(file_path, "r", encoding="utf-8") as infile:
                            outfile.write(infile.read())
                            outfile.write("\n")
                    except Exception as e:
                        outfile.write(f"--- Lỗi khi đọc file này: {e} ---\n")
                    
                    print(f"Đã thêm: {relative_path}")

    print(f"\nHoàn thành! Tất cả code đã được lưu vào: {output_filename}")

if __name__ == "__main__":
    merge_python_files()