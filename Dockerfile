FROM node:24-bookworm-slim AS web
WORKDIR /web
COPY web/package*.json ./
RUN npm ci --no-fund --no-audit
COPY web/ ./
RUN npm run build

FROM python:3.14-slim
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY research_agent/ research_agent/
COPY data/ data/
COPY references/ references/
COPY prompts/ prompts/
COPY --from=web /web/dist/ web/dist/
EXPOSE 8507
CMD ["python", "-m", "research_agent.server", "--host", "0.0.0.0"]
