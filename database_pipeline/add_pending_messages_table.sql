-- Migration: Add pending_messages table for progressive response pattern
-- This table stores in-progress messages so frontend can poll for status
-- Run this SQL in your Supabase SQL Editor

-- Create pending_messages table for tracking in-progress chat requests
CREATE TABLE IF NOT EXISTS public.pending_messages (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  session_id UUID REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
  content TEXT NOT NULL,  -- The user's question
  status TEXT NOT NULL DEFAULT 'pending',  -- pending, entities_ready, complete, error
  route_used TEXT,  -- direct, rag, sql, hybrid (set after decide_route)
  identified_entities JSONB,  -- Entities found by decide_route (available early)
  response TEXT,  -- Final response (available when complete)
  table_data JSONB,  -- Table data from SQL queries (available when complete)
  response_time_ms INTEGER,  -- Total processing time
  error_message TEXT,  -- Error message if status is 'error'
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for efficient polling
CREATE INDEX IF NOT EXISTS idx_pending_messages_user_id ON public.pending_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_pending_messages_status ON public.pending_messages(status);
CREATE INDEX IF NOT EXISTS idx_pending_messages_created_at ON public.pending_messages(created_at DESC);

-- Enable Row Level Security
ALTER TABLE public.pending_messages ENABLE ROW LEVEL SECURITY;

-- RLS policies - users can only access their own pending messages
CREATE POLICY "Users can view own pending messages" ON public.pending_messages
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can create own pending messages" ON public.pending_messages
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own pending messages" ON public.pending_messages
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own pending messages" ON public.pending_messages
  FOR DELETE USING (auth.uid() = user_id);

-- Grant permissions
GRANT ALL ON public.pending_messages TO anon, authenticated;

-- Function to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION public.update_pending_message_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update timestamp
DROP TRIGGER IF EXISTS pending_message_updated ON public.pending_messages;
CREATE TRIGGER pending_message_updated
  BEFORE UPDATE ON public.pending_messages
  FOR EACH ROW EXECUTE FUNCTION public.update_pending_message_timestamp();

-- Optional: Auto-cleanup function to delete old pending messages (run periodically)
-- Messages older than 5 minutes that are still pending or completed can be cleaned up
CREATE OR REPLACE FUNCTION public.cleanup_old_pending_messages()
RETURNS INTEGER AS $$
DECLARE
  deleted_count INTEGER;
BEGIN
  DELETE FROM public.pending_messages 
  WHERE created_at < NOW() - INTERVAL '5 minutes';
  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

