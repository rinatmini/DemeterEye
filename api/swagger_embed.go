// swagger_embed.go
package main

import _ "embed"

//go:embed openapi.yaml
var openapiYAML []byte
