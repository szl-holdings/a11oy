/**
 * MCP Client for Tribe Agents
 * Joe, Josie, and all agents use this to call MCP tools
 */

const MCP_BASE_URL = process.env.MCP_BASE_URL || 'http://localhost:8080/api/mcp';

/**
 * Call any MCP tool by name with arguments
 * @param {string} toolName - e.g., "google.gmail.search", "web.browse", "db.properties.list"
 * @param {object} args - Tool arguments
 * @returns {Promise<{ok: boolean, result?: any, error?: string}>}
 */
export async function callTool(toolName, args = {}) {
  try {
    const res = await fetch(`${MCP_BASE_URL}/invoke`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tool: toolName, arguments: args })
    });

    const data = await res.json();
    return data;
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

/**
 * List all available MCP tools
 * @returns {Promise<Array<{name, description}>>}
 */
export async function listTools() {
  try {
    const res = await fetch(`${MCP_BASE_URL}/tools`);
    const data = await res.json();
    return data.tools || [];
  } catch (err) {
    return [];
  }
}

// ============================================
// GMAIL HELPERS (for Joe & Josie)
// ============================================

export const gmail = {
  /** Search emails with query syntax */
  async search(query, maxResults = 50) {
    return callTool('google.gmail.search', { query, maxResults });
  },

  /** Get full message by ID */
  async getMessage(messageId) {
    return callTool('google.gmail.getMessage', { messageId });
  },

  /** Get conversation thread */
  async getThread(threadId) {
    return callTool('google.gmail.getThread', { threadId });
  },

  /** Send email */
  async send(to, subject, body, options = {}) {
    return callTool('google.gmail.send', { to, subject, body, ...options });
  },

  /** List all labels */
  async listLabels() {
    return callTool('google.gmail.listLabels', {});
  },

  /** Add/remove labels on message */
  async modifyLabels(messageId, addLabelIds = [], removeLabelIds = []) {
    return callTool('google.gmail.modifyLabels', { messageId, addLabelIds, removeLabelIds });
  },

  /** Download attachment */
  async getAttachment(messageId, attachmentId) {
    return callTool('google.gmail.getAttachment', { messageId, attachmentId });
  }
};

// ============================================
// DRIVE HELPERS (for Joe & Josie)
// ============================================

export const drive = {
  /** List files, optionally filter by folder */
  async listFiles(query = '', pageSize = 100) {
    return callTool('google.drive.listFiles', { q: query, pageSize });
  },

  /** Get file content (exports Google Docs as text) */
  async getFile(fileId, mimeType) {
    return callTool('google.drive.getFile', { fileId, mimeType });
  },

  /** Deep traverse folder recursively */
  async traverseFolder(folderId = 'root', maxDepth = 10) {
    return callTool('google.drive.traverseFolder', { folderId, maxDepth });
  },

  /** Full-text search across Drive */
  async searchContent(query, fileType) {
    return callTool('google.drive.searchContent', { query, fileType });
  }
};

// ============================================
// CALENDAR HELPERS
// ============================================

export const calendar = {
  /** List events in date range */
  async listEvents(timeMin, timeMax, maxResults = 100) {
    return callTool('google.calendar.listEvents', { timeMin, timeMax, maxResults });
  },

  /** Get single event */
  async getEvent(eventId) {
    return callTool('google.calendar.getEvent', { eventId });
  },

  /** Create new event */
  async createEvent(summary, start, end, options = {}) {
    return callTool('google.calendar.createEvent', { summary, start, end, ...options });
  }
};

// ============================================
// WEB RESEARCH HELPERS (for Alloy, Iris, all)
// ============================================

export const web = {
  /** Search the web */
  async search(query, maxResults = 5, timeFilter) {
    return callTool('web.search', { query, maxResults, timeFilter });
  },

  /** Browse a specific URL */
  async browse(url, textOnly = true) {
    return callTool('web.browse', { url, textOnly });
  },

  /** Deep research on a topic */
  async research(topic, depth = 'standard', sources = 5) {
    return callTool('web.research', { topic, depth, sources });
  }
};

// ============================================
// DATABASE HELPERS (for Joe & Josie)
// ============================================

export const db = {
  /** Execute read-only SQL query */
  async query(sql) {
    return callTool('db.query', { sql });
  },

  /** List all properties */
  async listProperties() {
    return callTool('db.properties.list', {});
  },

  /** Get recent expenses */
  async recentExpenses(limit = 50) {
    return callTool('db.expenses.recent', { limit });
  },

  /** Get pending tasks */
  async pendingTasks(limit = 50) {
    return callTool('db.tasks.pending', { limit });
  },

  /** List vendors */
  async listVendors() {
    return callTool('db.vendors.list', {});
  }
};

// ============================================
// SLACK HELPERS
// ============================================

export const slack = {
  /** Send message to Slack */
  async send(message, channel, username) {
    return callTool('slack.send', { message, channel, username });
  },

  /** Send formatted alert */
  async alert(title, message, priority = 'medium', channel) {
    return callTool('slack.alert', { title, message, priority, channel });
  }
};

// ============================================
// DOCUMENT HELPERS
// ============================================

export const doc = {
  /** Read text file */
  async readText(filePath) {
    return callTool('doc.readText', { filePath });
  },

  /** List directory contents */
  async listDirectory(dirPath, recursive = false) {
    return callTool('doc.listDirectory', { dirPath, recursive });
  },

  /** Extract text from PDF */
  async extractPdf(filePath) {
    return callTool('doc.extractPdf', { filePath });
  },

  /** Analyze image metadata */
  async analyzeImage(filePath) {
    return callTool('doc.analyzeImage', { filePath });
  }
};

// ============================================
// JOSIE'S SPECIALIZED WORKFLOW HELPERS
// ============================================

export const josieWorkflows = {
  /** Weekly email scan for all properties */
  async weeklyEmailScan() {
    // Search for invoices, vendor communications, urgent items
    const queries = [
      'subject:invoice after:7d',
      'subject:payment after:7d',
      'subject:urgent after:7d',
      'from:vendor after:7d'
    ];
    
    const results = [];
    for (const query of queries) {
      const res = await gmail.search(query, 20);
      if (res.ok && res.result.messages) {
        results.push({ query, messages: res.result.messages });
      }
    }
    
    return {
      scanDate: new Date().toISOString(),
      categories: results,
      totalFound: results.reduce((sum, r) => sum + (r.messages?.length || 0), 0)
    };
  },

  /** Get Drive documents for weekly report */
  async gatherWeeklyReportDocs() {
    // Search for recent documents
    const res = await drive.searchContent('weekly report OR property update', 'document');
    return res;
  },

  /** Check pending tasks across properties */
  async checkPendingTasks() {
    return db.pendingTasks(100);
  }
};

// ============================================
// JOE'S SPECIALIZED WORKFLOW HELPERS
// ============================================

export const joeWorkflows = {
  /** Vendor coordination check */
  async vendorStatusCheck() {
    // Get recent vendor emails
    const vendorEmails = await gmail.search('from:vendor OR subject:vendor after:7d', 50);
    
    // Get pending work orders/tasks
    const pending = await db.pendingTasks(100);
    
    // Get vendor list from DB
    const vendors = await db.listVendors();
    
    return {
      recentCommunications: vendorEmails,
      pendingTasks: pending,
      activeVendors: vendors
    };
  },

  /** Financial snapshot */
  async financialSnapshot(days = 30) {
    return db.recentExpenses(100);
  },

  /** Property compliance check */
  async complianceCheck() {
    // Search for compliance-related emails
    const queries = [
      'subject:insurance after:30d',
      'subject:permit after:30d',
      'subject:inspection after:30d',
      'subject:COI after:30d'
    ];
    
    const results = [];
    for (const query of queries) {
      const res = await gmail.search(query, 10);
      results.push({ query, result: res });
    }
    
    return results;
  }
};

// Export everything
export default {
  callTool,
  listTools,
  gmail,
  drive,
  calendar,
  web,
  db,
  slack,
  doc,
  josieWorkflows,
  joeWorkflows
};
