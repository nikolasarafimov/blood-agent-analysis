FROM node:20-alpine AS build
WORKDIR /app
ARG REACT_APP_API_URL
ENV REACT_APP_API_URL=$REACT_APP_API_URL
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
RUN printf '%s\n' \
'server {' \
'  listen 80;' \
'  server_name _;' \
'  root /usr/share/nginx/html;' \
'  index index.html;' \
'  location / { try_files $uri $uri/ /index.html; }' \
'  location ~* \.(?:js|css|png|jpg|jpeg|svg|ico|woff2|woff|ttf)$ {' \
'    expires 30d;' \
'    add_header Cache-Control "public, max-age=2592000, immutable";' \
'    try_files $uri =404;' \
'  }' \
'  location = /index.html { add_header Cache-Control "no-cache"; }' \
'}' \
> /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]