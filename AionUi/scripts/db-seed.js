/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 *
 * Database seeding script for development
 */

require('dotenv').config();
const { drizzle } = require('drizzle-orm/node-postgres');
const { Pool } = require('pg');
const bcrypt = require('bcrypt');

const connectionString =
  process.env.DATABASE_URL || 'postgresql://hivemind:hivemind_dev_password@localhost:5432/hivemind';

const pool = new Pool({ connectionString });
const db = drizzle(pool);

async function seed() {
  console.log('🌱 Seeding database...\n');

  try {
    // Seed users
    console.log('👥 Creating users...');
    const passwordHash = await bcrypt.hash('password123', 10);

    await pool.query(`
      INSERT INTO users (username, email, password_hash, role, display_name, email_verified)
      VALUES
        ('admin', 'admin@hivemind.local', $1, 'admin', 'Admin User', true),
        ('demo', 'demo@hivemind.local', $1, 'user', 'Demo User', true)
      ON CONFLICT (username) DO NOTHING
    `, [passwordHash]);

    console.log('  ✅ Users created');

    // Seed providers
    console.log('\n🔌 Creating AI providers...');
    await pool.query(`
      INSERT INTO providers (name, type, enabled, config)
      VALUES
        ('Google AI', 'google', true, '{"region": "us-central1"}'),
        ('Anthropic', 'anthropic', true, '{"version": "2023-06-01"}'),
        ('OpenAI', 'openai', true, '{"organization": "hivemind"}')
      ON CONFLICT (name) DO NOTHING
    `);

    console.log('  ✅ Providers created');

    // Seed models
    console.log('\n🤖 Creating AI models...');
    const providersResult = await pool.query('SELECT id, type FROM providers');
    const providers = providersResult.rows;

    for (const provider of providers) {
      if (provider.type === 'google') {
        await pool.query(`
          INSERT INTO models (name, display_name, provider_id, model_id, capabilities, context_window, max_output_tokens, enabled)
          VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
          ON CONFLICT (name) DO NOTHING
        `, [
          'gemini-2.0-flash',
          'Gemini 2.0 Flash',
          provider.id,
          'gemini-2.0-flash-exp',
          JSON.stringify({ chat: true, vision: true, functionCalling: true, streaming: true }),
          1000000,
          8192,
          true
        ]);
      } else if (provider.type === 'anthropic') {
        await pool.query(`
          INSERT INTO models (name, display_name, provider_id, model_id, capabilities, context_window, max_output_tokens, enabled)
          VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
          ON CONFLICT (name) DO NOTHING
        `, [
          'claude-sonnet-4.5',
          'Claude Sonnet 4.5',
          provider.id,
          'claude-sonnet-4-5-20250929',
          JSON.stringify({ chat: true, vision: true, functionCalling: true, streaming: true }),
          200000,
          16384,
          true
        ]);
      } else if (provider.type === 'openai') {
        await pool.query(`
          INSERT INTO models (name, display_name, provider_id, model_id, capabilities, context_window, max_output_tokens, enabled)
          VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
          ON CONFLICT (name) DO NOTHING
        `, [
          'gpt-4o',
          'GPT-4o',
          provider.id,
          'gpt-4o',
          JSON.stringify({ chat: true, vision: true, functionCalling: true, streaming: true }),
          128000,
          16384,
          true
        ]);
      }
    }

    console.log('  ✅ Models created');

    // Seed sample conversations
    console.log('\n💬 Creating sample conversations...');
    const usersResult = await pool.query("SELECT id FROM users WHERE username = 'demo'");
    if (usersResult.rows.length > 0) {
      const userId = usersResult.rows[0].id;

      const convResult = await pool.query(`
        INSERT INTO conversations (user_id, name, platform, model, message_count)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
      `, [userId, 'Welcome to Hivemind', 'hivemind', 'claude-sonnet-4.5', 2]);

      const conversationId = convResult.rows[0].id;

      // Add welcome messages
      await pool.query(`
        INSERT INTO messages (conversation_id, role, content)
        VALUES
          ($1, 'user', 'Hello! What is Hivemind?'),
          ($1, 'assistant', 'Hivemind is a unified AI collaboration platform that brings together multiple AI assistants (Gemini, Claude, Codex, and more) into one powerful interface. You can chat with different AI models, manage conversations, create automated workflows with skills and cron jobs, and collaborate across multiple agents. How can I help you explore Hivemind today?')
      `, [conversationId]);

      console.log('  ✅ Sample conversation created');
    }

    console.log('\n✅ Database seeding completed!\n');
    console.log('📝 Default credentials:');
    console.log('  Admin: admin@hivemind.local / password123');
    console.log('  Demo:  demo@hivemind.local / password123\n');

  } catch (error) {
    console.error('\n❌ Seeding failed:');
    console.error(error);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

seed();
