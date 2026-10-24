import { Redirect } from "expo-router";

/** Unknown links (old routes, typos) go back through the entry route. */
export default function NotFound() {
  return <Redirect href="/" />;
}
