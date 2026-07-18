#!/usr/bin/env bash
set -euo pipefail

# AMBER Alert Plugin Setup Script
# Guides deployment and validates configuration

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
echo "==========================================="
echo " TAK AMBER Alert Plugin Setup"
echo "==========================================="
echo -e "${NC}"

# Check if .env exists
if [ -f .env ]; then
    echo -e "${YELLOW}⚠ .env file already exists${NC}"
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Using existing .env file"
        ENV_EXISTS=true
    else
        ENV_EXISTS=false
    fi
else
    ENV_EXISTS=false
fi

if [ "$ENV_EXISTS" = false ]; then
    cp .env.template .env
    echo -e "${GREEN}✓ Created .env from template${NC}"
    
    # Interactive configuration
    echo ""
    echo "=== TAK-Server Configuration ==="
    read -p "TAK-Server IP/hostname: " TAK_HOST
    read -p "TAK-Server port (default 8089): " TAK_PORT
    TAK_PORT=${TAK_PORT:-8089}
    
    # Update .env
    sed -i "s/^TAK_HOST=.*/TAK_HOST=$TAK_HOST/" .env
    sed -i "s/^TAK_PORT=.*/TAK_PORT=$TAK_PORT/" .env
    
    echo ""
    echo "=== Geofence Configuration ==="
    echo "Define your Area of Operation (AO)"
    read -p "Geofence name: " GF_NAME
    read -p "Latitude: " GF_LAT
    read -p "Longitude: " GF_LON
    read -p "Radius (km): " GF_RADIUS
    
    sed -i "s|^AMBER_GEOFENCES=.*|AMBER_GEOFENCES=$GF_NAME:$GF_LAT:$GF_LON:$GF_RADIUS|" .env
    
    echo ""
    echo "=== Satellite Categories ==="
    echo "Available: stations, visual, active, starlink, gps, military"
    read -p "Categories (comma-separated, default: stations,visual,gps): " AMBER_CATS
    AMBER_CATS=${AMBER_CATS:-stations,visual,gps}
    sed -i "s/^AMBER_TLE_CATEGORIES=.*/AMBER_TLE_CATEGORIES=$AMBER_CATS/" .env
    
    echo -e "${GREEN}✓ Configuration saved to .env${NC}"
fi

# Certificate validation
echo ""
echo "=== mTLS Certificate Validation ==="
CERTS_DIR="./certs"
mkdir -p "$CERTS_DIR"

CERT_FILES=("client.pem" "client-key.pem" "ca.pem")
CERTS_OK=true

for cert in "${CERT_FILES[@]}"; do
    if [ -f "$CERTS_DIR/$cert" ]; then
        echo -e "${GREEN}✓ Found: $cert${NC}"
    else
        echo -e "${RED}✗ Missing: $cert${NC}"
        CERTS_OK=false
    fi
done

if [ "$CERTS_OK" = false ]; then
    echo ""
    echo -e "${YELLOW}⚠ Certificates not found in ./certs/${NC}"
    echo ""
    echo "Generate certificates from your TAK-Server:"
    echo "  cd /opt/tak/certs"
    echo "  ./makeCert.sh client amber-alert-plugin"
    echo ""
    echo "Then copy to this host:"
    echo "  scp amber-alert-plugin.pem user@$(hostname):$(pwd)/certs/client.pem"
    echo "  scp amber-alert-plugin-key.pem user@$(hostname):$(pwd)/certs/client-key.pem"
    echo "  scp ca.pem user@$(hostname):$(pwd)/certs/ca.pem"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled. Place certificates in ./certs/ and re-run setup.sh"
        exit 1
    fi
else
    # Validate cert permissions
    chmod 600 "$CERTS_DIR"/*.pem 2>/dev/null || true
    echo -e "${GREEN}✓ Certificate permissions set${NC}"
fi

# Docker check
echo ""
echo "=== Docker Validation ==="
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found${NC}"
    echo "Install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}✗ docker-compose not found${NC}"
    echo "Install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${GREEN}✓ Docker installed${NC}"

# Create data directory
mkdir -p data logs
echo -e "${GREEN}✓ Created data and logs directories${NC}"

# Vendor takgateway library
echo ""
echo "=== Vendoring takgateway Library ==="
if [ ! -d "src/takgateway" ]; then
    if [ -d "../tak-plugin-gateway/src/takgateway" ]; then
        cp -r ../tak-plugin-gateway/src/takgateway src/
        echo -e "${GREEN}✓ Vendored takgateway from local gateway repo${NC}"
    else
        echo -e "${YELLOW}⚠ tak-plugin-gateway not found in ../tak-plugin-gateway${NC}"
        echo "You'll need to either:"
        echo "  1. Clone tak-plugin-gateway adjacent to this repo"
        echo "  2. Install via pip: pip install takgateway"
        echo "  3. Manually copy takgateway/ into src/"
    fi
else
    echo -e "${GREEN}✓ takgateway already present${NC}"
fi

# Summary
echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}✓ Setup Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Review .env configuration"
echo "  2. Ensure certificates are in ./certs/"
echo "  3. Build and start:"
echo "     ${CYAN}docker-compose build${NC}"
echo "     ${CYAN}docker-compose up -d${NC}"
echo ""
echo "  4. Check logs:"
echo "     ${CYAN}docker-compose logs -f${NC}"
echo ""
echo "  5. Health check:"
echo "     ${CYAN}docker-compose ps${NC}"
echo ""
