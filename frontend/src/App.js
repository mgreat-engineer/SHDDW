import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Show, SignIn, SignUp } from "@clerk/react";
import ClerkAuthProvider from "@/components/auth/ClerkAuthProvider";
import AuthLayout from "@/pages/AuthLayout";
import Workspace from "@/pages/Workspace";
import Landing from "@/pages/Landing";
import { Toaster } from "@/components/ui/sonner";

const IN_APP = (() => {
  if (new URLSearchParams(window.location.search).get("app") === "1") sessionStorage.setItem("shadow-app", "1");
  return sessionStorage.getItem("shadow-app") === "1";
})();

function Home() {
  return (
    <>
      <Show when="signed-in"><Workspace /></Show>
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
