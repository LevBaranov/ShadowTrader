import { Container } from "@mui/material";
import { Outlet } from "react-router-dom";
import Header from "../components/Header";

export default function MainLayout() {
  return (
    <Container maxWidth="lg">
      <Header />
      <Outlet />
    </Container>
  );
}