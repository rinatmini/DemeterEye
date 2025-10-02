# syntax=docker/dockerfile:1

FROM golang:1.24 AS build
WORKDIR /app

# 1) deps cache
COPY go.mod go.sum ./
RUN go mod download

# 2) source
COPY . .

# 3) build only the main package, not ./...
ARG TARGETOS
ARG TARGETARCH
RUN CGO_ENABLED=0 GOOS=${TARGETOS:-linux} GOARCH=${TARGETARCH:-amd64} \
    go build -o server ./   

# Runtime
FROM gcr.io/distroless/base-debian12
ENV PORT=8080
EXPOSE 8080
COPY --from=build /app/server /server
USER 65532:65532
CMD ["/server"]
