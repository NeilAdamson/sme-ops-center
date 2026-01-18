FROM node:20-slim

WORKDIR /app

# Use existing node user (UID 1000) - node images already have this user
# Ensure proper ownership
RUN chown -R node:node /app

# Copy package files
COPY package.json ./

# Install dependencies (use npm install for scaffold; switch to npm ci when package-lock.json exists)
RUN npm install --only=production && \
    chown -R node:node /app

# Copy application
COPY . .

# Switch to non-root user (node user already exists in base image)
USER node

EXPOSE 3000

CMD ["node", "server.js"]
