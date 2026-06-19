import re
import unicodedata
from typing import List, Dict, Any


class TextCleaner:
    """Làm sạch và chuẩn hóa nội dung văn bản tiếng Việt/Anh"""

    def clean_text(self, text: str) -> str:
        if not text:
            return ""

        # Chuẩn hóa Unicode (giữ nguyên dấu tiếng Việt chuẩn)
        text = unicodedata.normalize("NFC", text)

        # Xóa ký tự null và control characters (trừ newline, tab)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

        # Chuẩn hóa các loại khoảng trắng đặc biệt
        text = text.replace('\xa0', ' ')  # Non-breaking space
        text = text.replace('\u200b', '')  # Zero-width space

        # Chuẩn hóa các loại dấu nháy
        text = text.replace('“', '"').replace('”', '"')
        text = text.replace('‘', "'").replace('’', "'")

        # Xóa khoảng trắng liên tiếp trên cùng một dòng (giữ newline)
        text = re.sub(r'[ \t]+', ' ', text)

        # Xóa nhiều dòng trống liên tiếp (giữ tối đa 2 dòng trống liên tiếp)
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Trim khoảng trắng ở đầu/cuối của từng dòng
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)

        return text.strip()

    def clean_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Làm sạch nội dung của danh sách documents và lọc bỏ các documents rỗng"""
        cleaned_docs = []
        for doc in documents:
            cleaned_content = self.clean_text(doc.get("content", ""))
            if cleaned_content:
                new_doc = doc.copy()
                new_doc["content"] = cleaned_content
                cleaned_docs.append(new_doc)
        return cleaned_docs
