import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import AsyncStorage from "@react-native-async-storage/async-storage";
import type { Account } from "./api";

interface User {
  user_id: string;
  email: string;
  org_id: string;
  token: string;
}

interface AppStore {
  user: User | null;
  selectedAccount: Account | null;
  setUser: (user: User | null) => void;
  setSelectedAccount: (account: Account | null) => void;
}

export const useStore = create<AppStore>()(
  persist(
    (set) => ({
      user: null,
      selectedAccount: null,
      setUser: (user) => set({ user }),
      setSelectedAccount: (account) => set({ selectedAccount: account }),
    }),
    {
      name: "kosha-store",
      storage: createJSONStorage(() => AsyncStorage),
    }
  )
);
