# 📚 NTUT-BOOKSYSTEM (北科大團購書本系統)

這是一個專為學校設計的「團購書本系統」。透過這個系統，學生們可以一起集中團購教科書，避免每個人單獨購買，進而達到省運費與書錢的目的。

## ✨ 系統功能 (Features)

- **學生端**：
  - 登入並填寫基本資料。
  - 查看並參與當前學期（Semester）開放團購的書本。
  - 在開放編輯的期限內（Deadline）修改個人資料或團購訂單。
- **管理員端**：
  - 管理學期與設定購買期限。
  - 新增、修改或刪除要販賣的書名與相關資訊。
  - 總覽所有學生的訂購狀態與清單。

## 🛠️ 技術架構 (Tech Stack)

- **後端框架**: Python Flask
- **資料庫**: SQLAlchemy (支援 SQLite 用於本機開發，PostgreSQL 用於正式環境)
- **伺服器**: Gunicorn
- **環境變數管理**: python-dotenv

---

## 🚀 如何開始使用 (Getting Started)

如果您想自行架設與運行這個系統，您可以選擇在「本機開發」或直接「部署到雲端服務 (如 Render)」。

### 1. 準備工作

請先 Fork 或 Clone 這個專案到您的本地端：
```bash
git clone https://github.com/您的帳號/NTUT-BOOKSYSTEM.git
cd NTUT-BOOKSYSTEM
```

### 2. 環境變數設定

在專案根目錄建立一個 `.env` 檔案，並設定以下變數：

```ini
# 必填設定
SECRET_KEY=你的安全密鑰_請隨意設定一個難以猜測的字串
ADMIN_USER=自訂管理員帳號
ADMIN_PASSWORD=自訂管理員密碼

# 選填設定 (若無設定，預設會使用本機的 sqlite:///local.db)
# DATABASE_URL=postgresql://user:password@localhost/dbname

# 選填設定 (若設定為 true，系統會在啟動時自動建立測試用的預設資料)
# SEED_DB=true
```

### 3. 在本機運行 (Run Locally)

1. **建立虛擬環境與安裝依賴套件**:
   ```bash
   python -m venv venv
   # macOS / Linux
   source venv/bin/activate  
   # Windows
   venv\Scripts\activate
   
   pip install -r requirements.txt
   ```

2. **啟動伺服器**:
   ```bash
   python app.py
   ```
   伺服器啟動後，請開啟瀏覽器前往 `http://127.0.0.1:5000`。系統會在第一次啟動時自動建立所需的資料庫 Table。

### 4. 部署到雲端 (Deploy to Render)

作者推薦使用 [Render](https://render.com/) 來部署此系統，它適合運行這類型的專案。

1. 在 Render 上建立一個 **Web Service**，並連結您 Fork 過去的 GitHub Repository。
2. (可選) 建立一個 **PostgreSQL** 資料庫，並將其 Database URL 複製起來。
3. 在 Web Service 的 `Environment` 設定區，新增您在 `.env` 裡所設定的所有環境變數。如果有建立資料庫，請將 `DATABASE_URL` 填入您的 PostgreSQL 連結。
4. 部署設定：
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app` (或是依賴 Render 預設的 Python Web App 設定)
5. 部署完成後，系統會自動在第一次啟動時建立好資料庫。接著您就可以使用管理員帳號登入後台，開始「建立要販賣的書名與價格等資訊」了！

## 🤝 貢獻 (Contributing)

如果您對本系統有任何改進想法，歡迎提交 Issue 或是 Pull Request！

---
*Created to help students save money and make group buying easier.*
