-- Migration: Add subscription and role columns to profiles table
-- Run this script to add the subscription and role columns with default values

-- Add subscription column if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'profiles' 
        AND column_name = 'subscription'
    ) THEN
        ALTER TABLE public.profiles 
        ADD COLUMN subscription TEXT DEFAULT 'basic';
    END IF;
END $$;

-- Add role column if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'profiles' 
        AND column_name = 'role'
    ) THEN
        ALTER TABLE public.profiles 
        ADD COLUMN role TEXT DEFAULT 'user';
    END IF;
END $$;

-- Update existing rows to have default values if they are NULL
UPDATE public.profiles 
SET subscription = 'basic' 
WHERE subscription IS NULL;

UPDATE public.profiles 
SET role = 'user' 
WHERE role IS NULL;

