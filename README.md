# NTUT Book System

供班級團購教科書使用的 Flask 系統。

## 必要環境變數

```env
SECRET_KEY=請使用長且隨機的字串
ADMIN_USER=管理員帳號
ADMIN_PASSWORD=管理員密碼
DATABASE_URL=資料庫連線網址
```

正式部署務必固定設定 `SECRET_KEY`；若每次啟動都改變，既有登入狀態會失效。

## 自動測試

GitHub Actions 會在推送至 `main`／`master`，以及對這些分支建立 Pull Request 時執行：

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

測試使用記憶體內的臨時 SQLite，完全不連線或修改正式資料庫。只要測試失敗，CI 就會顯示紅燈。建議在 GitHub 分支保護規則中把 `build-and-test` 設成必要檢查。

資料庫啟動升級只會新增缺少的欄位，不會刪除或重建既有資料表。正式資料仍應另外使用託管平台提供的定期備份功能。
