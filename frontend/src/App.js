import "@/App.css";
import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Show, SignIn, SignUp } from "@clerk/react";
import ClerkAuthProvider from "@/components/auth/ClerkAuthProvider";
import AuthLayout from "@/pages/AuthLayout";
import Landing from "@/pages/Landing";
import { Toaster } from "@/components/ui/sonner";

const Workspace = lazy(() => import("@/pages/Workspace"));
const Loading = () => <div className="h-screen flex items-center justify-center text-sm text-[#5F6368]" data-testid="app-loading">Loading Shadow…</div>;

const IN_APP = (() => {
  const q = new URLSearchParams(window.location.search);
  if (q.get("app") === "1") sessionStorage.setItem("shadow-app", "1");
  if (q.get("link")) sessionStorage.setItem("shadow-link", q.get("link"));
  return sessionStorage.getItem("shadow-app") === "1";
})();

function Home() {
  return (
    <>
      <Show when="signed-in"><Suspense fallback={<Loading />}><Workspace /></Suspense></Show>
      <Show when="signed-out">{IN_APP ? <Navigate to="/sign-in" replace /> : <Landing />}</Show>
    </>
  );
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <ClerkAuthProvider>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/download" element={<Landing />} />
            <Route path="/sign-in/*" element={<AuthLayout><SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" withSignUp /></AuthLayout>} />
            <Route path="/sign-up/*" element={<AuthLayout><SignUp routing="path" path="/sign-up" signInUrl="/sign-in" /></AuthLayout>} />
          </Routes>
        </ClerkAuthProvider>
      </BrowserRouter>
      <Toaster theme="light" position="bottom-right" offset="110px" richColors />
    </div>
  );
}

export default App;
