import { useEffect } from "react";
import { useRouter } from "expo-router";
import { isLoggedIn } from "../lib/auth";

export default function IndexScreen() {
  const router = useRouter();
  useEffect(() => {
    isLoggedIn().then((loggedIn) => {
      router.replace(loggedIn ? "/(app)/audits" : "/login");
    });
  }, []);
  return null;
}
