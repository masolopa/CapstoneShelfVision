import { createContext, useContext } from 'react';
import type { User } from './auth';

export const SessionContext = createContext<User | null>(null);
export const useSession = () => useContext(SessionContext);
