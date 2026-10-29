import { useEffect, useState } from 'react';
import api from '../api/api';
import { errorMessage } from './Operations';

const SEND_EVERY_MS = 15000; // the server accepts 12 updates a minute

/**
 * While `enabled`, watch the phone's GPS and send the position to `logPath`
 * at most every 15 seconds. Returns the latest position and a plain status.
 */
export default function useGpsSharing(logPath, enabled) {
  const [position, setPosition] = useState(null);
  const [status, setStatus] = useState({ state: 'waiting', text: 'Waiting for location permission.' });

  useEffect(() => {
    if (!enabled) return undefined;
    if (!navigator.geolocation) {
      setStatus({ state: 'blocked', text: 'This browser cannot share location.' });
      return undefined;
    }
    let alive = true;
    let lastSent = 0;
    let sending = false;

    const watch = navigator.geolocation.watchPosition(
      async (fix) => {
        if (!alive) return;
        const coords = [fix.coords.latitude, fix.coords.longitude];
        setPosition(coords);
        if (sending || Date.now() - lastSent < SEND_EVERY_MS) return;
        sending = true;
        lastSent = Date.now();
        try {
          await api.post(logPath, { lat: coords[0], lng: coords[1] });
          if (alive) setStatus({ state: 'sharing', text: `Sharing location · last sent ${new Date().toLocaleTimeString()}` });
        } catch (err) {
          if (alive) setStatus({ state: 'error', text: `Location not sent: ${errorMessage(err)}` });
        } finally {
          sending = false;
        }
      },
      (err) => {
        if (!alive) return;
        setStatus(err.code === 1
          ? { state: 'blocked', text: 'Location blocked. Allow it in your browser settings.' }
          : { state: 'waiting', text: 'Looking for GPS signal. Your round is still saved.' });
      },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 },
    );

    return () => {
      alive = false;
      navigator.geolocation.clearWatch(watch);
    };
  }, [logPath, enabled]);

  return { position, status };
}
