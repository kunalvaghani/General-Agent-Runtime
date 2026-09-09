"use client";
export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  return <section className="panel" role="alert"><h1>Something went wrong</h1>
    <p>The page could not load. Your saved tasks are unaffected.</p><button onClick={reset}>Try again</button></section>;
}
