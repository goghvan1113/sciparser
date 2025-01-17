# Reference Parser Workflow

## 1. Process Input
### Input: 分为三种（1）文献的pdf文件（2）文献标题，直接进行下一步（3）作者名字,直接进行下一步
### Process: input为文献的pdf文件时，使用Grobid进行Header解析得到Header结果的xml文件，包括title, authors, year, journal, volume, issue, pages, doi, url, abstract, keywords, etc（获取不到就为空）.
### Output: 文献标题或者作者名字

## 2. Scholarly Query（参考search.ipynb和scholarly Docs）
### document level:如果上一步输入是文献的pdf文件和文献标题，则需要先进行文献引用搜索，假设为文献A，得到引用文献A的所有文献集合B的详细信息包括title, authors, year, journal, volume, issue, pages, doi, url, abstract, keywords, etc获取不到就为空）；
### author level:如果上一步输入是作者名字，则需要进行作者名字搜索，得到作者谷歌学术上的论文集合M，按照引用量从高到低排序选取M集合中前2篇论文（可以修改），分别进行document level的搜索，得到文献集合B1和B2。
### Output: 文献集合B、或者文献集合B1和B2的标题集合


## 3. PyPaperBot Download(参考download.ipynb)
### 使用PyPaperBot下载文献集合B、或者文献集合B1和B2的pdf文件，标题集合作为query，下载的pdf文件保存到本地数据库中
### Output: 文献集合B、或者文献集合B1和B2的pdf文件
### 包含是否下载成功的日志

## 4. ReferenceParser 
### 以文献集合B为例，已知文献集合B为引用文献A的所有文献，其中文献集合B中的元素标题为b1,b2,b3,b4,b5,b6,b7,b8,b9,b10；对应的pdf文件为b1.pdf,b2.pdf,b3.pdf,b4.pdf,b5.pdf,b6.pdf,b7.pdf,b8.pdf,b9.pdf,b10.pdf；解析所有pdf文件的参考文献和原文中对应的citation statement，即full_context，以及所在的section，存储到本地为json文件



## 5. Gradio界面
### 在main.py的基础上添加新的内容，同process input节
### 输出可以为各个阶段的输出

## 6. 数据库
### 将下载的pdf文件、对应的pdf文件的grobid解析结果以及reference parser的结果存储到本地数据库中（采用sqlite）

