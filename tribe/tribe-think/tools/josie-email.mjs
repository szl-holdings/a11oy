/**
 * Josie Email Tools — MCP Integration (Correct Path)
 * Uses API server MCP directly, bypasses Odysseus restrictions
 */

import { gmail, drive, calendar } from './mcp-client.mjs';

// Tool: gmail_search — Direct MCP call
export const gmail_search = {
  name: "gmail_search",
  description: "Search Gmail using MCP. Query syntax: from:, to:, subject:, after:, before:, has:attachment, is:unread, etc.",
  input_schema: {
    type: "object",
    properties: {
      query: { type: "string", description: "Gmail search query" },
      maxResults: { type: "number", default: 50 }
    },
    required: ["query"]
  },
  async execute({ query, maxResults = 50 }) {
    return gmail.search(query, maxResults);
  }
};

// Tool: gmail_get — Get full message
export const gmail_get = {
  name: "gmail_get",
  description: "Get full email content by message ID",
  input_schema: {
    type: "object",
    properties: {
      messageId: { type: "string" }
    },
    required: ["messageId"]
  },
  async execute({ messageId }) {
    return gmail.getMessage(messageId);
  }
};

// Tool: gmail_get_attachment
export const gmail_get_attachment = {
  name: "gmail_get_attachment",
  description: "Download attachment from Gmail message",
  input_schema: {
    type: "object",
    properties: {
      messageId: { type: "string" },
      attachmentId: { type: "string" }
    },
    required: ["messageId", "attachmentId"]
  },
  async execute({ messageId, attachmentId }) {
    return gmail.getAttachment(messageId, attachmentId);
  }
};

// Tool: drive_search
export const drive_search = {
  name: "drive_search",
  description: "Search Google Drive files by content",
  input_schema: {
    type: "object",
    properties: {
      query: { type: "string" },
      fileType: { type: "string", enum: ["document", "spreadsheet", "pdf"] }
    },
    required: ["query"]
  },
  async execute({ query, fileType }) {
    return drive.searchContent(query, fileType);
  }
};

// Tool: drive_traverse
export const drive_traverse = {
  name: "drive_traverse",
  description: "Deep folder traversal in Drive",
  input_schema: {
    type: "object",
    properties: {
      folderId: { type: "string", default: "root" },
      maxDepth: { type: "number", default: 10 }
    }
  },
  async execute({ folderId = "root", maxDepth = 10 }) {
    return drive.traverseFolder(folderId, maxDepth);
  }
};

// Tool: drive_open — open a pasted Google Drive/Docs/Sheets LINK (or bare ID) and read it
function extractDriveId(link) {
  if (!link || typeof link !== "string") return null;
  const s = link.trim();
  let m = s.match(/\/d\/([a-zA-Z0-9_-]{20,})/);            // /d/FILEID/
  if (m) return m[1];
  m = s.match(/[?&]id=([a-zA-Z0-9_-]{20,})/);               // ?id= / &id=
  if (m) return m[1];
  m = s.match(/\/folders\/([a-zA-Z0-9_-]{20,})/);          // /folders/FILEID
  if (m) return m[1];
  if (/^[a-zA-Z0-9_-]{20,}$/.test(s)) return s;             // bare id
  return null;
}

export const drive_open = {
  name: "drive_open",
  description: "Open a Google Drive / Google Sheets / Google Docs LINK that Rosa pastes (or a bare file ID) and read its full content. Handles docs.google.com and drive.google.com URLs. For Google Sheets it returns the tabular data; for Docs, the text; for PDFs/other files, the extracted text or metadata. Use this ANY time Rosa shares a Drive link and asks you to look at, read, summarize, check, or work from a file or spreadsheet.",
  input_schema: {
    type: "object",
    properties: {
      link: { type: "string", description: "The full Google Drive/Docs/Sheets URL, or a bare file ID." }
    },
    required: ["link"]
  },
  async execute({ link }) {
    const id = extractDriveId(link);
    if (!id) return "I couldn't find a Google Drive file ID in that link. Please paste the full https://… link (e.g. https://docs.google.com/spreadsheets/d/…/edit).";
    const res = await drive.getFile(id);
    if (res && res.ok === false) return "Couldn't open that file: " + (res.error || "unknown error") + ". It may need to be shared with the workspace Google account.";
    return res;
  }
};

// Tool: calendar_list
export const calendar_list = {
  name: "calendar_list",
  description: "List calendar events for date range",
  input_schema: {
    type: "object",
    properties: {
      days: { type: "number", default: 7 },
      maxResults: { type: "number", default: 50 }
    }
  },
  async execute({ days = 7, maxResults = 50 }) {
    const now = new Date();
    const timeMin = now.toISOString();
    const timeMax = new Date(now.getTime() + days * 24 * 60 * 60 * 1000).toISOString();
    return calendar.listEvents(timeMin, timeMax, maxResults);
  }
};

// Tool: scan_invoices — Uses MCP gmail.search
export const scan_invoices = {
  name: "scan_invoices",
  description: "Scan for invoices using multiple Gmail queries",
  input_schema: {
    type: "object",
    properties: {
      daysBack: { type: "number", default: 7 }
    }
  },
  async execute({ daysBack = 7 }) {
    const queries = [
      `subject:invoice after:${daysBack}d`,
      `subject:payment after:${daysBack}d`,
      `subject:bill after:${daysBack}d`,
      `has:attachment subject:invoice after:${daysBack}d`
    ];
    
    const results = [];
    for (const query of queries) {
      const res = await gmail.search(query, 25);
      if (res.ok && res.result?.messages) {
        results.push({ query, messages: res.result.messages });
      }
    }
    
    return {
      scanPeriod: `${daysBack} days`,
      queriesRun: results.length,
      results
    };
  }
};

// Tool: check_urgent
export const check_urgent = {
  name: "check_urgent",
  description: "Scan for urgent emails",
  input_schema: {
    type: "object",
    properties: {
      daysBack: { type: "number", default: 3 }
    }
  },
  async execute({ daysBack = 3 }) {
    const queries = [
      `subject:urgent after:${daysBack}d`,
      `subject:emergency after:${daysBack}d`,
      `is:starred after:${daysBack}d`
    ];
    
    const results = [];
    for (const query of queries) {
      const res = await gmail.search(query, 15);
      if (res.ok && res.result?.messages) {
        results.push({ query, messages: res.result.messages });
      }
    }
    
    return { queriesRun: results.length, results };
  }
};

// Export all tools
export const JOSIE_EMAIL_TOOLS = [
  gmail_search,
  gmail_get,
  gmail_get_attachment,
  drive_search,
  drive_traverse,
  drive_open,
  calendar_list,
  scan_invoices,
  check_urgent
];

export default JOSIE_EMAIL_TOOLS;
