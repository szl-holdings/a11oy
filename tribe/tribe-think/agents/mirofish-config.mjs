/**
 * Mirofish Agent Configuration
 * Data Intelligence + Analytics Specialist
 * Data analysis, pattern detection, predictive insights
 */

import { db, web, doc } from '../tools/mcp-client.mjs';
import { writeEntry } from '../../tribe/memory/tribe-memory.mjs';

export const MIROFISH_CONFIG = {
  name: "Mirofish",
  role: "Data Intelligence + Analytics Specialist",
  description: "Mirofish is the tribe's data scientist. He analyzes patterns, detects anomalies, builds predictive models, and turns raw data into actionable intelligence for SZL Holdings.",

  capabilities: [
    "Data analysis and pattern detection",
    "Predictive modeling",
    "Anomaly detection",
    "Financial trend analysis",
    "Property performance analytics",
    "Vendor performance scoring",
    "Custom report generation"
  ],

  tools: [
    {
      name: "analyzeExpenses",
      description: "Deep analysis of expense patterns",
      execute: async (args) => {
        const expenses = await db.recentExpenses(args.limit || 200);
        if (!expenses.ok) return { error: expenses.error };
        
        const data = expenses.result.expenses || [];
        
        // Calculate metrics
        const total = data.reduce((sum, e) => sum + (parseFloat(e.amount) || 0), 0);
        const byCategory = data.reduce((acc, e) => {
          acc[e.category] = (acc[e.category] || 0) + (parseFloat(e.amount) || 0);
          return acc;
        }, {});
        
        const byMonth = data.reduce((acc, e) => {
          const month = e.date?.substring(0, 7) || 'unknown';
          acc[month] = (acc[month] || 0) + (parseFloat(e.amount) || 0);
          return acc;
        }, {});
        
        return {
          total,
          count: data.length,
          byCategory,
          byMonth,
          average: total / data.length
        };
      }
    },
    {
      name: "detectAnomalies",
      description: "Detect anomalies in financial data",
      execute: async (args) => {
        const expenses = await db.recentExpenses(100);
        const data = expenses.ok ? expenses.result.expenses || [] : [];
        
        const amounts = data.map(e => parseFloat(e.amount) || 0);
        const mean = amounts.reduce((a, b) => a + b, 0) / amounts.length;
        const stdDev = Math.sqrt(amounts.reduce((sq, n) => sq + Math.pow(n - mean, 2), 0) / amounts.length);
        
        const anomalies = data.filter(e => {
          const amount = parseFloat(e.amount) || 0;
          return Math.abs(amount - mean) > 2 * stdDev;
        });
        
        return { anomalies, threshold: mean + 2 * stdDev, mean, stdDev };
      }
    },
    {
      name: "vendorScorecard",
      description: "Generate vendor performance scorecard",
      execute: async (args) => {
        const vendors = await db.listVendors();
        const expenses = await db.recentExpenses(500);
        
        // Aggregate by vendor
        const vendorData = {};
        for (const e of (expenses.ok ? expenses.result.expenses || [] : [])) {
          if (!vendorData[e.vendor]) {
            vendorData[e.vendor] = { total: 0, count: 0, expenses: [] };
          }
          vendorData[e.vendor].total += parseFloat(e.amount) || 0;
          vendorData[e.vendor].count += 1;
          vendorData[e.vendor].expenses.push(e);
        }
        
        // Score each vendor
        const scores = Object.entries(vendorData).map(([name, data]) => ({
          name,
          totalSpend: data.total,
          transactionCount: data.count,
          averageTransaction: data.total / data.count,
          score: Math.min(100, (data.count * 10) + (data.total / 100)) // Simple scoring
        }));
        
        return { vendors: scores.sort((a, b) => b.totalSpend - a.totalSpend) };
      }
    }
  ],

  workflows: {
    daily: [
      "Analyze previous day's expenses",
      "Check for anomalies",
      "Update predictive models"
    ],
    weekly: [
      "Generate vendor scorecards",
      "Property performance analysis",
      "Trend forecasting"
    ]
  },

  autonomy: {
    canAnalyze: true,
    canDetect: true,
    canReport: true,
    cannot: ["Make financial decisions", "Approve expenses"]
  },

  instructions: `
    You are Mirofish, the tribe's data intelligence specialist.
    
    YOUR MISSION:
    - Find patterns others miss
    - Predict problems before they happen
    - Turn data into decisions
    
    YOUR TOOLS:
    - db.* for data access
    - Statistical analysis
    - Pattern detection
    
    YOUR STANDARD:
    - Every insight must be actionable
    - Every prediction must have confidence
    - Every report must tell a story
    
    BE PRECISE. BE INSIGHTFUL. BE PREDICTIVE.
  `
};

export default MIROFISH_CONFIG;
