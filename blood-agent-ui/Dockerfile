FROM node:22-alpine AS build

WORKDIR /app

ARG REACT_APP_API_URL=http://localhost:8000
ARG REACT_APP_OCR_LANGUAGE=mkd+eng
ARG REACT_APP_PERSIST_SESSIONS=false

ENV REACT_APP_API_URL=${REACT_APP_API_URL} \
    REACT_APP_OCR_LANGUAGE=${REACT_APP_OCR_LANGUAGE} \
    REACT_APP_PERSIST_SESSIONS=${REACT_APP_PERSIST_SESSIONS} \
    GENERATE_SOURCEMAP=false

COPY package.json package-lock.json ./
RUN npm ci --include=dev --no-audit --no-fund

COPY public/ ./public/
COPY src/ ./src/

RUN npm run build

FROM nginx:stable-alpine

RUN printf '%s\n' \
      'add_header X-Content-Type-Options "nosniff" always;' \
      'add_header X-Frame-Options "DENY" always;' \
      'add_header Referrer-Policy "no-referrer" always;' \
      'add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;' \
      'add_header X-Robots-Tag "noindex, nofollow, noarchive" always;' \
      > /etc/nginx/security_headers.inc \
    && printf '%s\n' \
      'server {' \
      '  listen 80;' \
      '  server_name _;' \
      '  server_tokens off;' \
      '  root /usr/share/nginx/html;' \
      '  index index.html;' \
      '' \
      '  include /etc/nginx/security_headers.inc;' \
      '' \
      '  location / {' \
      '    try_files $uri $uri/ /index.html;' \
      '  }' \
      '' \
      '  location /static/ {' \
      '    include /etc/nginx/security_headers.inc;' \
      '    add_header Cache-Control "public, max-age=31536000, immutable" always;' \
      '    try_files $uri =404;' \
      '  }' \
      '' \
      '  location = /index.html {' \
      '    include /etc/nginx/security_headers.inc;' \
      '    add_header Cache-Control "no-store" always;' \
      '  }' \
      '' \
      '  location = /manifest.json {' \
      '    include /etc/nginx/security_headers.inc;' \
      '    add_header Cache-Control "no-cache" always;' \
      '  }' \
      '' \
      '  location = /logo.png {' \
      '    include /etc/nginx/security_headers.inc;' \
      '    add_header Cache-Control "public, max-age=3600" always;' \
      '  }' \
      '' \
      '  location = /robots.txt {' \
      '    include /etc/nginx/security_headers.inc;' \
      '    add_header Cache-Control "no-cache" always;' \
      '  }' \
      '}' \
      > /etc/nginx/conf.d/default.conf \
    && nginx -t

COPY --from=build /app/build/ /usr/share/nginx/html/

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]