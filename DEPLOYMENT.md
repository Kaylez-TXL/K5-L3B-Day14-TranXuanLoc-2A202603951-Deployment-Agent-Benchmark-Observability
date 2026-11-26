# Day 14 — Deployment

## Trạng thái

- **Nền tảng dự kiến** — Railway.
- **Mã nguồn agent** — [`06-lab-complete/`](06-lab-complete/).
- **URL public** — Chờ deploy và kiểm tra.

## Cấu hình service

Tạo service agent từ nhánh `main` của bản fork và đặt **Root Directory** là `/06-lab-complete`. Railway phát hiện `Dockerfile` trong thư mục nguồn và dùng lệnh chạy của image. Đặt **Healthcheck Path** là `/health` trong cài đặt service. [Thư mục nguồn](https://docs.railway.com/deployments/monorepo) · [Dockerfile](https://docs.railway.com/builds/dockerfiles) · [Healthcheck](https://docs.railway.com/deployments/healthchecks)

Tạo Redis trong cùng project và môi trường với agent. Các biến của **service agent** như sau:

| Biến | Cách đặt |
| --- | --- |
| `ENVIRONMENT` | `production` |
| `REDIS_URL` | Chọn tham chiếu đến `REDIS_URL` của service Redis. |
| `AGENT_API_KEY` | Đặt giá trị riêng trong Railway Variables. |
| `PORT` | Railway cấp khi chạy. |

Sau khi deploy, tạo domain của **agent** trong **Settings → Networking → Public Networking → Generate Domain**. Agent kết nối Redis qua mạng riêng của project. [Railway Redis](https://docs.railway.com/databases/redis) · [Railway Domains](https://docs.railway.com/networking/domains/working-with-domains)

## Kiểm tra URL public

Chạy trong terminal WSL và nhập domain HTTPS cùng API key đã đặt trên Railway. Lệnh chỉ in mã HTTP.

```bash
read -rp 'URL public (https://...): ' BASE
BASE=${BASE%/}
read -rsp 'AGENT_API_KEY: ' AGENT_API_KEY
printf '\n'

curl -sS -o /dev/null -w 'GET /health: %{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w 'GET /ready: %{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w 'POST /ask thieu key: %{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'
curl -sS -o /dev/null -w 'POST /ask co key: %{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'

unset AGENT_API_KEY
```

| Phép thử | Mã mong đợi | Mã nhận được |
| --- | ---: | --- |
| `GET /health` | 200 | Chờ kiểm tra |
| `GET /ready` | 200 | Chờ kiểm tra |
| `POST /ask` thiếu key | 401 | Chờ kiểm tra |
| `POST /ask` có key | 200 | Chờ kiểm tra |

## Ảnh bằng chứng cần bổ sung

- `screenshots/dashboard.png` — Project Railway có agent và Redis.
- `screenshots/running.png` — Deployment agent đang chạy.
- `screenshots/test.png` — Terminal hiển thị bốn mã HTTP từ domain public.
