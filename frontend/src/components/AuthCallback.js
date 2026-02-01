import React, { useEffect, useState } from 'react';
import { supabase } from '../supabaseClient';
import PilarLoader from './PilarLoader';

const AuthCallback = ({ onAuthSuccess }) => {
  const [status, setStatus] = useState('processing');
  const [error, setError] = useState(null);

  useEffect(() => {
    // Listen for auth state changes (handles OAuth and email confirmation)
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'SIGNED_IN' && session) {
        setStatus('success');
        if (onAuthSuccess) {
          onAuthSuccess({
            id: session.user.id,
            email: session.user.email,
            username: session.user.user_metadata?.username || session.user.email?.split('@')[0]
          });
        }
        setTimeout(() => {
          window.location.href = '/';
        }, 1500);
      } else if (event === 'SIGNED_OUT') {
        setError('Sessió tancada');
        setStatus('error');
      }
    });

    return () => {
      subscription.unsubscribe();
    };
  }, [onAuthSuccess]);

  useEffect(() => {
    const handleAuthCallback = async () => {
      try {
        // Supabase automatically handles OAuth callbacks via hash fragments
        // and email confirmation via query parameters
        // We just need to get the session after the redirect
        
        // First, try to get the session (works for both OAuth and email confirmation)
        const { data: { session }, error: sessionError } = await supabase.auth.getSession();
        
        if (sessionError) {
          console.error('Session error:', sessionError);
        }

        // Also check for hash fragments (OAuth) or query params (email confirmation)
        const hashParams = new URLSearchParams(window.location.hash.substring(1));
        const urlParams = new URLSearchParams(window.location.search);
        
        const accessToken = hashParams.get('access_token');
        const errorParam = hashParams.get('error') || urlParams.get('error');
        const errorDescription = hashParams.get('error_description') || urlParams.get('error_description');
        const token = urlParams.get('token');
        const type = urlParams.get('type');

        if (errorParam) {
          setError(errorDescription || errorParam);
          setStatus('error');
          return;
        }

        // If we have a session, we're good
        if (session) {
          setStatus('success');
          // Redirect to home page after a brief delay
          setTimeout(() => {
            window.location.href = '/';
          }, 1500);
          return;
        }

        // If we have a token in query params (email confirmation), verify it
        if (token && type) {
          try {
            const { data, error } = await supabase.auth.verifyOtp({
              token_hash: token,
              type: type
            });

            if (error) {
              setError(error.message);
              setStatus('error');
              return;
            }

            if (data?.session) {
              setStatus('success');
              setTimeout(() => {
                window.location.href = '/';
              }, 1500);
              return;
            }
          } catch (verifyError) {
            console.error('Verify OTP error:', verifyError);
            setError('Error verificant el correu electrònic');
            setStatus('error');
            return;
          }
        }

        // If we have an access token in hash (OAuth), wait a moment for Supabase to process it
        if (accessToken) {
          // Give Supabase a moment to process the OAuth callback
          setTimeout(async () => {
            const { data: { session: newSession }, error: newError } = await supabase.auth.getSession();
            if (newSession) {
              setStatus('success');
              setTimeout(() => {
                window.location.href = '/';
              }, 1500);
            } else if (newError) {
              setError(newError.message);
              setStatus('error');
            } else {
              setError('No se pudo obtener la sesión');
              setStatus('error');
            }
          }, 1000);
          return;
        }

        // If we get here, something went wrong
        setError('No se encontró información de autenticación');
        setStatus('error');
      } catch (err) {
        console.error('Auth callback error:', err);
        setError(err.message || 'Error procesando la autenticación');
        setStatus('error');
      }
    };

    handleAuthCallback();
  }, [onAuthSuccess]);

  if (status === 'processing') {
    return (
      <div style={{ 
        display: 'flex', 
        flexDirection: 'column', 
        alignItems: 'center', 
        justifyContent: 'center', 
        minHeight: '100vh',
        padding: '2rem'
      }}>
        <PilarLoader />
        <p style={{ marginTop: '2rem', fontSize: '1.1rem' }}>Processant autenticació...</p>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div style={{ 
        display: 'flex', 
        flexDirection: 'column', 
        alignItems: 'center', 
        justifyContent: 'center', 
        minHeight: '100vh',
        padding: '2rem',
        textAlign: 'center'
      }}>
        <div style={{ 
          background: '#fee',
          border: '1px solid #fcc',
          borderRadius: '8px',
          padding: '2rem',
          maxWidth: '500px'
        }}>
          <h2 style={{ color: '#c33', marginBottom: '1rem' }}>Error d'autenticació</h2>
          <p style={{ color: '#666', marginBottom: '1.5rem' }}>{error}</p>
          <button
            onClick={() => window.location.href = '/'}
            style={{
              background: '#3498db',
              color: 'white',
              border: 'none',
              padding: '0.75rem 1.5rem',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '1rem'
            }}
          >
            Tornar a l'inici
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      alignItems: 'center', 
      justifyContent: 'center', 
      minHeight: '100vh',
      padding: '2rem'
    }}>
      <div style={{ 
        background: '#efe',
        border: '1px solid #cfc',
        borderRadius: '8px',
        padding: '2rem',
        textAlign: 'center'
      }}>
        <h2 style={{ color: '#3c3', marginBottom: '1rem' }}>✓ Autenticació exitosa</h2>
        <p style={{ color: '#666' }}>Redirigint...</p>
      </div>
    </div>
  );
};

export default AuthCallback;

