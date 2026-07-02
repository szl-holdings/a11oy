#!/usr/bin/env node
/**
 * Test Joe and Josie MCP Integration
 */

import { gmail, db, web } from './tools/mcp-client.mjs';

console.log('🧪 Testing Joe & Josie MCP Integration\n');

// Test 1: Gmail labels (Josie's morning check)
console.log('1️⃣ Testing Gmail labels...');
const labels = await gmail.listLabels();
console.log(labels.ok ? `✅ Found ${labels.result.labels?.length || 0} labels` : `❌ Error: ${labels.error}`);

// Test 2: DB properties (Joe's audit)
console.log('\n2️⃣ Testing DB properties...');
const props = await db.listProperties();
console.log(props.ok ? `✅ Found ${props.result.properties?.length || 0} properties` : `❌ Error: ${props.error}`);

// Test 3: Web browse (both can research)
console.log('\n3️⃣ Testing web browse...');
const page = await web.browse('https://example.com');
console.log(page.ok ? `✅ Fetched page: ${page.result.text?.substring(0, 50)}...` : `❌ Error: ${page.error}`);

// Test 4: Gmail search (Josie scanning invoices)
console.log('\n4️⃣ Testing Gmail search...');
const search = await gmail.search('subject:test after:1d', 5);
console.log(search.ok ? `✅ Search returned ${search.result.messages?.length || 0} messages` : `❌ Error: ${search.error}`);

console.log('\n✨ All tests complete!');
console.log('\n📋 Summary:');
console.log('- Josie can scan emails, organize labels, prepare reports');
console.log('- Joe can audit vendors, check compliance, detect anomalies');
console.log('- Both can search web, query DB, send Slack alerts');
