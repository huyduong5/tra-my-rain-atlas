#!/usr/bin/env bash
# Đưa website lên GitHub và bật GitHub Pages (chạy lại nhiều lần vẫn an toàn).
# Yêu cầu: đã đăng nhập GitHub CLI bằng `gh auth login`.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO=tra-my-rain-atlas

gh auth status >/dev/null 2>&1 || { echo "Chưa đăng nhập: chạy 'gh auth login' trước."; exit 1; }
OWNER=$(gh api user -q .login)
echo "Tài khoản GitHub: ${OWNER}"

# Điền tên tài khoản vào README và đường dẫn repo
if grep -q "OWNER" README.md assets/js/routes.js; then
  sed -i "s/OWNER/${OWNER}/g" README.md assets/js/routes.js
  git add README.md assets/js/routes.js
  git commit -q -m "Điền đường dẫn GitHub Pages cho tài khoản ${OWNER}"
fi

# Tạo repo công khai nếu chưa có, rồi push
if ! gh repo view "${OWNER}/${REPO}" >/dev/null 2>&1; then
  gh repo create "${REPO}" --public --source . --remote origin \
    --description "Tra cứu và phân tích mưa giờ trạm Trà My (Quảng Nam) 2008–2017: thống kê, cực trị, R95p/R99p, chu kỳ lặp lại"
fi
git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/${OWNER}/${REPO}.git"
git push -u origin main

# Bật GitHub Pages chế độ GitHub Actions
if ! gh api "repos/${OWNER}/${REPO}/pages" >/dev/null 2>&1; then
  gh api -X POST "repos/${OWNER}/${REPO}/pages" -f build_type=workflow >/dev/null
else
  gh api -X PUT "repos/${OWNER}/${REPO}/pages" -f build_type=workflow >/dev/null || true
fi

URL="https://${OWNER}.github.io/${REPO}/"
gh repo edit "${OWNER}/${REPO}" --homepage "${URL}" \
  --add-topic rainfall --add-topic climate --add-topic vietnam --add-topic data-visualization \
  --add-topic extreme-precipitation --add-topic github-pages >/dev/null

# Chạy lại workflow (lần push đầu có thể diễn ra trước khi Pages được bật)
gh workflow run deploy.yml --ref main >/dev/null 2>&1 || true
echo "Đã đẩy mã nguồn: https://github.com/${OWNER}/${REPO}"
echo "Website (sau 1–3 phút): ${URL}"
