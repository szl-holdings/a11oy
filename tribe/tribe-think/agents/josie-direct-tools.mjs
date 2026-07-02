/**
 * Josie Direct Tools — Bypass Odysseus Wrapper
 * These tools call the API server MCP directly, no redirects
 */

const API_BASE = 'http://127.0.0.1:8080/api';

async function callMcp(tool, args) {
  const res = await fetch(`${API_BASE}/mcp/invoke`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tool, arguments: args })
  });
  return res.json();
}

// Direct Gmail search — no wrapper, no redirect
export const josie_gmail_search = {
  name: "josie_gmail_search",
  description: "Search Gmail directly. Returns actual messages, not redirects. Use for invoice scanning, vendor emails, urgent items.",
  input_schema: {
    type: "object",
    properties: {
      query: { type: "string", description: "Gmail search query (e.g., 'subject:invoice after:7d')" },
      maxResults: { type: "number", default: 50 }
    },
    required: ["query"]
  },
  async execute({ query, maxResults = 50 }) {
    const result = await callMcp('google.gmail.search', { query, maxResults });
    if (!result.ok) return { error: result.error || 'Search failed' };
    return {
      query,
      messagesFound: result.result?.messages?.length || 0,
      messages: result.result?.messages || [],
      resultSizeEstimate: result.result?.resultSizeEstimate || 0
    };
  }
};

// Get full message
export const josie_gmail_get = {
  name: "josie_gmail_get",
  description: "Get full email content by message ID. Use after search to read body, headers, attachments.",
  input_schema: {
    type: "object",
    properties: {
      messageId: { type: "string", description: "Gmail message ID from search results" }
    },
    required: ["messageId"]
  },
  async execute({ messageId }) {
    const result = await callMcp('google.gmail.getMessage', { messageId, format: 'full' });
    if (!result.ok) return { error: result.error || 'Get message failed' };
    return {
      messageId,
      headers: result.result?.payload?.headers || [],
      subject: result.result?.payload?.headers?.find(h => h.name === 'Subject')?.value || 'No subject',
      from: result.result?.payload?.headers?.find(h => h.name === 'From')?.value || 'Unknown',
      date: result.result?.payload?.headers?.find(h => h.name === 'Date')?.value || '',
      body: result.result?.snippet || '',
      hasAttachments: (result.result?.payload?.parts || []).some(p => p.filename)
    };
  }
};

// Drive search
export const josie_drive_search = {
  name: "josie_drive_search",
  description: "Search Google Drive for documents, spreadsheets, invoices.",
  input_schema: {
    type: "object",
    properties: {
      query: { type: "string", description: "Search text" },
      fileType: { type: "string", enum: ["document", "spreadsheet", "pdf"], description: "Filter by type" }
    },
    required: ["query"]
  },
  async execute({ query, fileType }) {
    const result = await callMcp('google.drive.searchContent', { query, fileType });
    if (!result.ok) return { error: result.error || 'Drive search failed' };
    return {
      query,
      filesFound: result.result?.files?.length || 0,
      files: result.result?.files || []
    };
  }
};

// Calendar events
export const josie_calendar_list = {
  name: "josie_calendar_list",
  description: "List calendar events for a date range. Default: next 7 days.",
  input_schema: {
    type: "object",
    properties: {
      days: { type: "number", default: 7, description: "Days ahead to look" },
      maxResults: { type: "number", default: 50 }
    }
  },
  async execute({ days = 7, maxResults = 50 }) {
    const now = new Date();
    const timeMin = now.toISOString();
    const timeMax = new Date(now.getTime() + days * 24 * 60 * 60 * 1000).toISOString();
    const result = await callMcp('google.calendar.listEvents', { timeMin, timeMax, maxResults });
    if (!result.ok) return { error: result.error || 'Calendar query failed' };
    return {
      timeRange: { from: timeMin, to: timeMax },
      eventsFound: result.result?.events?.length || 0,
      events: result.result?.events || []
    };
  }
};

// Invoice scanner — combines search + get for common patterns
export const josie_scan_invoices = {
  name: "josie_scan_invoices",
  description: "Scan for invoices across all property mailboxes. Returns structured invoice data.",
  input_schema: {
    type: "object",
    properties: {
      daysBack: { type: "number", default: 7, description: "Days to scan" }
    }
  },
  async execute({ daysBack = 7 }) {
    const queries = [
      `subject:invoice after:${daysBack}d`,
      `subject:payment due after:${daysBack}d`,
      `subject:bill after:${daysBack}d`,
      `has:attachment subject:invoice after:${daysBack}d`
    ];
    
    const allInvoices = [];
    
    for (const query of queries) {
      const searchResult = await callMcp('google.gmail.search', { query, maxResults: 25 });
      if (searchResult.ok && searchResult.result?.messages) {
        for (const msg of searchResult.result.messages.slice(0, 10)) {
          const fullResult = await callMcp('google.gmail.getMessage', { messageId: msg.id });
          if (fullResult.ok) {
            const headers = fullResult.result?.payload?.headers || [];
            allInvoices.push({
              messageId: msg.id,
              threadId: msg.threadId,
              subject: headers.find(h => h.name === 'Subject')?.value || 'No subject',
              from: headers.find(h => h.name === 'From')?.value || 'Unknown',
              date: headers.find(h => h.name === 'Date')?.value || '',
              snippet: fullResult.result?.snippet || ''
            });
          }
        }
      }
    }
    
    // Deduplicate by threadId
    const unique = Array.from(new Map(allInvoices.map(i => [i.threadId, i])).values());
    
    return {
      scanPeriod: `${daysBack} days`,
      invoicesFound: unique.length,
      invoices: unique,
      readyForReview: true
    };
  }
};

// Export all direct tools
export const JOSIE_DIRECT_TOOLS = [
  josie_gmail_search,
  josie_gmail_get,
  josie_drive_search,
  josie_calendar_list,
  josie_scan_invoices
];

export default JOSIE_DIRECT_TOOLS;
