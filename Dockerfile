# Ponto Falante · imagem única: Angular compilado servido pelo Spring Boot.
# Estágio 1: frontend (Angular)  →  Estágio 2: backend (Maven, com o Angular em /static)  →  Estágio 3: runtime (JRE, não root)

# ---------- 1. Frontend ----------
FROM node:24.16-alpine AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build -- --configuration production

# ---------- 2. Backend ----------
FROM eclipse-temurin:21-jdk-alpine AS backend
WORKDIR /src/backend
COPY backend/.mvn/ .mvn/
COPY backend/mvnw backend/pom.xml ./
# O Maven Central às vezes responde 429 aos runners compartilhados: até 3 tentativas com espera.
RUN chmod +x mvnw && for i in 1 2 3; do ./mvnw -q -B dependency:go-offline && exit 0; echo "Maven: tentativa $i falhou"; sleep $((i * 20)); done; exit 1
COPY backend/src/ src/
# O build do Angular substitui o placeholder de static/
RUN rm -rf src/main/resources/static
COPY --from=frontend /src/frontend/dist/frontend/browser/ src/main/resources/static/
RUN ./mvnw -q -B -DskipTests package && cp target/pontofalante.jar /app.jar

# ---------- 3. Runtime ----------
FROM eclipse-temurin:21-jre-alpine
RUN addgroup -S app && adduser -S -G app -u 10001 app && apk add --no-cache wget
WORKDIR /app
COPY --from=backend --chown=app:app /app.jar /app/app.jar
USER 10001
ENV PORT=8080 \
    JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=70 -XX:+UseSerialGC -XX:TieredStopAtLevel=1 -Xss512k -Djava.security.egd=file:/dev/./urandom"
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD wget -qO- "http://127.0.0.1:${PORT}/actuator/health" | grep -q '"UP"' || exit 1
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
