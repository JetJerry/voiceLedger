import { useContext } from 'react';
import { SoundboxContext, SoundboxContextType } from '../context/SoundboxContext';

export function useSoundbox(): SoundboxContextType {
  const context = useContext(SoundboxContext);
  if (!context) {
    throw new Error('useSoundbox must be used within a SoundboxProvider');
  }
  return context;
}
