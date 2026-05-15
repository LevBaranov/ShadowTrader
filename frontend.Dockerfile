# ---------------- DEV ----------------
FROM node:20-alpine AS dev

WORKDIR /app

COPY frontend/package*.json ./
RUN npm install

COPY frontend/. .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]


# ---------------- BUILD ----------------
FROM node:20-alpine AS build

WORKDIR /app

COPY frontend/package*.json ./
RUN npm install

COPY frontend/. .
RUN npm run build


# ---------------- PROD ----------------
FROM nginx:alpine AS prod

COPY --from=build /app/dist /usr/share/nginx/html

RUN rm /etc/nginx/conf.d/default.conf
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]