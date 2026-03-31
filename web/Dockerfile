FROM node:20-alpine AS dependencies

WORKDIR /app

COPY package*.json ./
RUN npm ci


FROM dependencies AS development

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]


FROM dependencies AS build

ARG NEXT_PUBLIC_API_BASE_URL=
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}

COPY . .

RUN npm run build


FROM nginx:1.27-alpine AS production

COPY deploy/nginx-static.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/out /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
