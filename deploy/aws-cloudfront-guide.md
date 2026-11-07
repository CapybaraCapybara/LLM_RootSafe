# 🌐 AWS CloudFront + Backend Deployment Guide (RootSafe Arborist)

เอกสารแนะนำสถาปัตยกรรมและการตั้งค่า **AWS CloudFront** ร่วมกับ Backend Container สำหรับระบบ **RootSafe Arborist**

---

## 🏗️ 1. สถาปัตยกรรมระบบ (Architecture Overview)

```
[ผู้ใช้งานทั่วโลก (Browsers)]
          │
          │ HTTPS (Port 443) / Global Edge Locations
          ▼
┌─────────────────────────────────────────────────────────────┐
│                 AWS CloudFront Distribution                 │
│                                                             │
│   ├── Path: /api/*  ──► [Origin 1: FastAPI Container]       │
│   │                     (App Runner / ECS / EC2)            │
│   │                     • Cache: CachingDisabled            │
│   │                     • Response Buffering: Disabled      │
│   │                     • Supports SSE Real-time Streaming  │
│   │                                                         │
│   └── Path: Default (*) ──► [Origin 2: S3 Bucket / UI]      │
│                             (static/ HTML, CSS, JS)         │
│                             • Cache: CachingOptimized       │
│                             • Gzip / Brotli Compression     │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
[Class LLM Proxy: https://llm.nat-d.uk/v1]
```

> [!IMPORTANT]
> **ข้อกำหนดสำคัญสำหรับ SSE (Server-Sent Events) บน CloudFront:**
> CloudFront จะต้องปิดการ Cache และการ Buffer บน Path `/api/*` เพื่อให้ Token และ Live Tool Pills สตรีมแบบ Real-time ไปยังเบราว์เซอร์ของผู้ใช้ได้ทันทีโดยไม่ดีเลย์

---

## 🚀 2. ขั้นตอนการ Deploy: วิธีที่ 1 — AWS App Runner + CloudFront (แนะนำ ง่ายและเร็วที่สุด)

AWS App Runner เป็น Managed Container Service ของ AWS ที่รัน Container จาก Dockerfile โดยตรงโดยไม่ต้องดูแล EC2 หรือ Load Balancer

### ขั้นที่ 2.1: Build & Push Docker Image ขึ้น Amazon ECR
```bash
# 1. ล็อกอินเข้า Amazon ECR (เปลี่ยน <aws-account-id> และ <region>)
aws ecr get-login-password --region ap-southeast-1 | docker login --username AWS --password-stdin <aws-account-id>.dkr.ecr.ap-southeast-1.amazonaws.com

# 2. สร้าง ECR Repository
aws ecr create-repository --repository-name rootsafe-arborist --region ap-southeast-1

# 3. Build และ Tag Docker Image
docker build -t rootsafe-arborist .
docker tag rootsafe-arborist:latest <aws-account-id>.dkr.ecr.ap-southeast-1.amazonaws.com/rootsafe-arborist:latest

# 4. Push Image ขึ้น ECR
docker push <aws-account-id>.dkr.ecr.ap-southeast-1.amazonaws.com/rootsafe-arborist:latest
```

### ขั้นที่ 2.2: สร้าง AWS App Runner Service
1. เข้า **AWS Management Console** ➔ ไปที่ **AWS App Runner**
2. เลือก **Create Service** ➔ Container image: เลือก image จาก ECR ที่เพิ่ง push
3. กำหนดค่า Port: `8000`
4. ตั้งค่า Environment Variables:
   * `OPENAI_API_KEY`: `<your-class-proxy-key>`
   * `OPENAI_BASE_URL`: `https://llm.nat-d.uk/v1`
   * `MODEL`: `gemma-4-E4B-it`
   * `RAG_MIN_SCORE`: `0.35`
5. รอ App Runner สร้างเสร็จ จะได้ URL เช่น: `https://xxxxxx.ap-southeast-1.awsapprunner.com`

---

## ⚡ 3. การสร้างและตั้งค่า AWS CloudFront Distribution

### ขั้นที่ 3.1: สร้าง Distribution
1. ไปที่ **CloudFront Console** ➔ คลิก **Create distribution**
2. **Origin domain**: ใส่ URL ของ App Runner เช่น `xxxxxx.ap-southeast-1.awsapprunner.com`
3. **Protocol**: เลือก `HTTPS only`

### ขั้นที่ 3.2: ตั้งค่า Cache Behavior สำหรับ SSE Stream (`/api/*`)
สร้าง Cache Behavior ลำดับที่ 0:
* **Path pattern**: `/api/*`
* **Origin**: เลือก App Runner Origin
* **Viewer protocol policy**: `Redirect HTTP to HTTPS`
* **Allowed HTTP methods**: `GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE`
* **Cache policy**: เลือก `Managed-CachingDisabled`
* **Origin request policy**: เลือก `Managed-AllViewerExceptHostHeader`
* **Response headers policy**: ปิดการ Buffer เพื่อให้ SSE ทำงานลื่นไหล

### ขั้นที่ 3.3: ตั้งค่า Default Cache Behavior สำหรับ Static Web UI (`/*`)
* **Path pattern**: `Default (*)`
* **Viewer protocol policy**: `Redirect HTTP to HTTPS`
* **Allowed HTTP methods**: `GET, HEAD, OPTIONS`
* **Cache policy**: เลือก `Managed-CachingOptimized`
* **Compress objects automatically**: `Yes` (เปิด Gzip & Brotli)

---

## 🛠️ 4. การทดสอบ Local Container (ก่อน Deploy)

สามารถทดสอบรันด้วย Docker Compose ในเครื่องก่อนได้:
```bash
# รัน Container ผ่าน docker-compose
docker compose up -d --build

# ตรวจสอบสถานะ Health Check
curl http://localhost:8000/api/health

# ตรวจสอบ Log
docker compose logs -f
```
เมื่อพร้อมแล้ว URL ของ CloudFront เช่น `https://d123456abcdef8.cloudfront.net` จะสามารถเข้าใช้งานได้ทั่วโลกอย่างปลอดภัยและรวดเร็ว
