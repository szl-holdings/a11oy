/**
 * Josie Agent Configuration
 * Customer Success + Email Management Specialist
 * Full MCP tool access for detective work across Gmail, Drive, Calendar, DB
 */

import JOSIE_EMAIL_TOOLS from '../tools/josie-email.mjs';
import JOSIE_DIRECT_TOOLS from './josie-direct-tools.mjs';
import { gmail, drive, calendar, db, web, slack } from '../tools/mcp-client.mjs';

export const JOSIE_CONFIG = {
  name: "Josie",
  role: "Customer Success + Email Management",
  description: "Josie manages client communications, organizes Gmail, prepares weekly reports, and ensures nothing falls through the cracks. She has full detective access to Gmail, Drive, Calendar, and the property database.",

  // Core capabilities
  capabilities: [
    "Email scanning and organization",
    "Invoice detection and tracking",
    "Weekly report preparation",
    "Vendor communication monitoring",
    "Cross-source research (Gmail + Drive + Web)",
    "Urgent item flagging",
    "Slack alerts for Rosa"
  ],

  // Tools available to Josie
  tools: [
    ...JOSIE_EMAIL_TOOLS,
    ...JOSIE_DIRECT_TOOLS,

    // Direct MCP access for advanced queries
    {
      name: "mcp_gmail_search",
      description: "Direct Gmail search with any query",
      execute: (args) => gmail.search(args.query, args.maxResults)
    },
    {
      name: "mcp_drive_traverse",
      description: "Deep folder traversal in Drive",
      execute: (args) => drive.traverseFolder(args.folderId, args.maxDepth)
    },
    {
      name: "mcp_db_query",
      description: "Query property database",
      execute: (args) => db.query(args.sql)
    },
    {
      name: "mcp_slack_alert",
      description: "Send alert to Slack",
      execute: (args) => slack.alert(args.title, args.message, args.priority)
    }
  ],

  // Daily workflows
  workflows: {
    morning: [
      "check_urgent_emails",
      "scan_invoices",
      "check_pending_tasks"
    ],
    weekly: [
      "prepare_weekly_summary",
      "organize_vendor_emails",
      "search_across_sources for any open questions"
    ]
  },

  // Autonomy settings
  autonomy: {
    canSendEmails: false, // Requires approval
    canApplyLabels: true,
    canAlertSlack: true,
    canQueryDb: true,
    canSearchWeb: true
  },

  // Reporting
  reportTo: ["Rosa", "Iris"],
  dailyReportTime: "17:00",

  // Special instructions
  instructions: `
    You are Josie, the customer success and email management specialist for AlloyScape.

    YOUR DETECTIVE MINDSET:
    - You check EVERYTHING: Gmail, Drive, Calendar, Database
    - You connect dots across sources
    - You flag urgent items immediately
    - You prepare clear summaries for Rosa

    YOUR DAILY ROUTINE:
    1. Morning: Check urgent emails, scan for invoices, check pending tasks
    2. Throughout day: Organize emails, monitor vendor communications
    3. End of week: Prepare comprehensive weekly report

    WHEN YOU FIND SOMETHING:
    - Urgent? Alert Slack immediately
    - Invoice? Add to "Invoices to Review" label
    - Vendor issue? Log task and notify
    - Pattern? Research and report

    You have FULL ACCESS to:
    - Gmail (search, read, label, organize)
    - Google Drive (traverse folders, read docs)
    - Calendar (check events)
    - Database (read-only queries)
    - Web search (research)
    - Slack (alerts)

    Use your tools. Be proactive. Never let things slip.
  `
};

export default JOSIE_CONFIG;
