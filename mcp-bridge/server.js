const express = require('express');
const app = express();

const PORT = process.env.PORT || 3000;

// Middleware
app.use(express.json());

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'mcp-bridge' });
});

// Root endpoint
app.get('/', (req, res) => {
  res.json({ 
    message: 'SME Ops-Center MCP Bridge', 
    version: '0.1.0' 
  });
});

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`MCP Bridge server running on port ${PORT}`);
});
