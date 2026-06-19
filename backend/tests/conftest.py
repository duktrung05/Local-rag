"""
conftest.py - Pytest configuration cho RAG Chatbot v2
"""
import pytest
import sys
import os

# Thêm backend root vào Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def test_data_dir(tmp_path_factory):
    """Thư mục chứa dữ liệu test tạm thời"""
    return tmp_path_factory.mktemp("test_data")


@pytest.fixture(scope="session")
def sample_txt_file(test_data_dir):
    """File .txt mẫu dùng cho nhiều test"""
    f = test_data_dir / "sample.txt"
    f.write_text(
        "Đây là tài liệu mẫu về trí tuệ nhân tạo.\n\n"
        "Machine learning là nhánh của AI tập trung vào việc\n"
        "xây dựng hệ thống tự học từ dữ liệu.\n\n"
        "Deep learning sử dụng mạng nơ-ron nhiều lớp để giải quyết\n"
        "các bài toán phức tạp như nhận dạng hình ảnh và xử lý ngôn ngữ.",
        encoding="utf-8"
    )
    return f


@pytest.fixture(scope="session")
def sample_csv_file(test_data_dir):
    """File .csv mẫu"""
    f = test_data_dir / "sample.csv"
    f.write_text(
        "ten,tuoi,thanh_pho\n"
        "Nguyen Van An,25,Ha Noi\n"
        "Tran Thi Binh,30,Ho Chi Minh\n"
        "Le Van Cuong,28,Da Nang",
        encoding="utf-8"
    )
    return f
