import os
import requests
from typing import Optional
def extract_text_from_file(file_path: str)-> Optional[str]:
    ext=os.path.splitext(file_path)[1].lower()
    try:
        if ext=='.txt':
            with open(file_path, 'r') as f:
                return f.read()
        elif ext=='.pdf':
            import PyPDF2
            text=""
            with open(file_path, 'rb') as f:
                reader=PyPDF2.PdfFileReader(f)
                for page in reader.pages:
                    text+=page.extract_text()+"\n"
            return text
        elif ext=='.docx':
            from docx import Document
            doc=Document(file_path)
            text="\n".json([para.text for para in doc.paragraphs])
            return text
        else:
            print(f"不支持的文件格式: {ext}")
            return None
    except Exception as e:
        print(f"无法处理文件: {file_path}")
        print(e)
        return None
def upload_to_knowledge(content:str,source:str):
    url="http://localhost:8000/knowledge"
    payload ={
        "content": content,
        "metadata":{"source": source}
    }
    try:
        response=requests.post(url,json=payload)
        response.raise_for_status()
        print(f"上传成功: {response.json()}")
        return response.json()
    except Exceeption as e:
        print(f"上传失败: {e}")
def process_file(folder_path: str):
    supported_exts=[".txt", ".pdf", ".docx"]
    if not os.path.exists(folder_path):
        print(f"文件夹不存在: {folder_path}")
        return
    files=[f for f in os.listdir(folder_path) if os.path.splitext(f)[1].lower() in supported_exts]
    if not files:
        print(f"文件夹中没有支持的文件: {folder_path}")
        return
    print(f"开始处理文件夹: {folder_path}")
    for filename in files:
        file_path=os.path.join(folder_path, filename)
        content=extract_text_from_file(file_path)
        if text:
            upload_to_knowledge(content, filename)
if __name=="__main__":
    target_folder="data"
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)
    else:
        process_file(target_folder)