import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Show, SignIn, SignUp } from "@clerk/react";
import ClerkAuthProvider from "@/components/auth/ClerkAuthProvider";
import AuthLayout from "@/pages/AuthLayout";
import Workspace from "@/pages/Workspace";
import { Toaster } from "@/components/ui/sonner";

function Home() {
  return (
    <>
      <Show when="signed-in"><Workspace /></Show>
      <Show when="signed-out"><Navigate to="/sign-in" replace /></Show>
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
