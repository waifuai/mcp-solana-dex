"""
Solana DEX Animation Script

This script creates educational animations using Manim to visualize and explain the
Solana DEX server architecture and functionality. It provides visual explanations of:

1. System Architecture: Shows the relationship between MCP server, Solana DEX,
   order book persistence, and Solana RPC integration
2. Order Data Structure: Visualizes the fields and format of orders in the DEX
3. Core Functions: Explains the four main MCP tools (create, cancel, execute, get orders)
4. Order Execution Flow: Demonstrates the pre-check process before blockchain transactions
5. Summary: Provides an overview of the complete system

The animation serves as both documentation and educational material for understanding
how the DEX server works and integrates with the Solana blockchain.
"""

from manim import *
import numpy as np

class SolanaDEXAnimation(Scene):
    def construct(self):
        # Title
        title = Text("Solana DEX Server Animation", font_size=48, color=BLUE)
        subtitle = Text("Understanding the MCP-Based Token Exchange System", font_size=32, color=BLUE_B)
        subtitle.next_to(title, DOWN)

        self.play(Write(title))
        self.play(Write(subtitle))
        self.wait(2)
        self.play(FadeOut(title), FadeOut(subtitle))

        # Scene 1: Architecture Overview
        self.show_architecture()

        # Scene 2: Order Data Structure
        self.show_order_structure()

        # Scene 3: Core Functions
        self.show_core_functions()

        # Scene 4: Order Flow
        self.show_order_flow()

        # Scene 5: Summary
        self.show_summary()

    def show_architecture(self):
        # Create main components
        server_box = Rectangle(width=3, height=1, color=BLUE, fill_opacity=0.2)
        server_text = Text("MCP Server", font_size=20).move_to(server_box.get_center())
        server_text.shift(UP*2)

        dex_box = Rectangle(width=3, height=1, color=GREEN, fill_opacity=0.2)
        dex_text = Text("Solana DEX", font_size=20).move_to(dex_box.get_center())
        dex_box.next_to(server_box, DOWN, buff=1.0)
        dex_text.shift(DOWN*2)

        order_book = Rectangle(width=2, height=0.8, color=YELLOW, fill_opacity=0.2)
        order_book_text = Text("Order Book\n(JSON File)", font_size=14).move_to(order_book.get_center())
        order_book.next_to(dex_box, RIGHT, buff=2.5)
        order_book_text.shift(RIGHT*2)

        solana_box = Rectangle(width=2.5, height=1, color=PURPLE, fill_opacity=0.2)
        solana_text = Text("Solana RPC", font_size=18).move_to(solana_box.get_center())
        solana_box.next_to(dex_box, LEFT, buff=3.5)
        solana_text.shift(LEFT*2)

        # Position elements with better spacing
        server_box.move_to(UP * 2.5)

        # Draw connections
        server_to_dex = Arrow(server_box.get_bottom(), dex_box.get_top(), color=WHITE)
        dex_to_order = Arrow(dex_box.get_right(), order_book.get_left(), color=YELLOW)
        dex_to_solana = Arrow(dex_box.get_left(), solana_box.get_right(), color=PURPLE)

        # Animate
        self.play(Create(server_box), Write(server_text))
        self.wait(0.5)
        self.play(Create(dex_box), Write(dex_text))
        self.play(Create(server_to_dex))
        self.wait(0.5)
        self.play(Create(order_book), Write(order_book_text))
        self.play(Create(dex_to_order))
        self.wait(0.5)
        self.play(Create(solana_box), Write(solana_text))
        self.play(Create(dex_to_solana))

        # Add explanation
        explanation = Text("Architecture: MCP Server hosts DEX functionality\nwith JSON persistence and Solana RPC integration", font_size=20, color=WHITE)
        explanation.move_to(DOWN * 3)
        self.play(Write(explanation))
        self.wait(3)

        # Clear scene
        self.play(FadeOut(Group(server_box, server_text, dex_box, dex_text, order_book, order_book_text,
                              solana_box, solana_text, server_to_dex, dex_to_order, dex_to_solana, explanation)))

    def show_order_structure(self):
        # Order structure visualization
        order_title = Text("Order Data Structure", font_size=36, color=BLUE)
        self.play(Write(order_title))

        # Create order fields
        fields = [
            ("order_id", "str", "UUID"),
            ("ico_id", "str", "ICO identifier"),
            ("amount", "int", "Token amount (base units)"),
            ("price", "float", "Price per token in SOL"),
            ("owner", "str", "Seller's public key"),
            ("is_sell_order", "bool", "True for sell orders")
        ]

        field_boxes = VGroup()
        field_texts = VGroup()

        for i, (field_name, field_type, description) in enumerate(fields):
            box = Rectangle(width=6, height=0.6, color=GREEN, fill_opacity=0.1)
            text = Text(f"{field_name}: {field_type} - {description}", font_size=18)
            text.move_to(box.get_center())

            box.shift(DOWN * (i - 2.5) * 0.8)
            text.shift(DOWN * (i - 2.5) * 0.8)

            field_boxes.add(box)
            field_texts.add(text)

        # Animate field creation
        for box, text in zip(field_boxes, field_texts):
            self.play(Create(box), Write(text))
            self.wait(0.3)

        # Add JSON example
        json_example = Text('{\n  "order_id": "uuid-123",\n  "ico_id": "TOKEN_ICO",\n  "amount": 1000,\n  "price": 0.5,\n  "owner": "111...abc"\n}', font_size=16, color=YELLOW)
        json_example.move_to(RIGHT * 4 + UP * 2)

        self.play(Write(json_example))

        explanation = Text("Each order represents a sell offer for ICO tokens", font_size=20, color=WHITE)
        explanation.move_to(DOWN * 3)
        self.play(Write(explanation))

        self.wait(3)

        # Clear scene
        self.play(FadeOut(order_title), FadeOut(field_boxes), FadeOut(field_texts),
                 FadeOut(json_example), FadeOut(explanation))

    def show_core_functions(self):
        # Core functions visualization
        functions_title = Text("Core DEX Functions", font_size=36, color=BLUE)
        self.play(Write(functions_title))

        functions = [
            ("create_order", "Creates new sell orders", GREEN),
            ("cancel_order", "Cancels existing orders", RED),
            ("execute_order", "Performs pre-checks and updates order book", YELLOW),
            ("get_orders", "Retrieves current orders for an ICO", BLUE)
        ]

        func_boxes = VGroup()

        for i, (name, desc, color) in enumerate(functions):
            box = Rectangle(width=4, height=0.8, color=color, fill_opacity=0.2)
            func_name = Text(name, font_size=20, color=color)
            func_desc = Text(desc, font_size=14, color=WHITE)

            func_name.move_to(box.get_center() + UP * 0.2)
            func_desc.move_to(box.get_center() + DOWN * 0.2)

            box.shift(DOWN * (i - 1.5) * 1.2)
            func_name.shift(DOWN * (i - 1.5) * 1.2)
            func_desc.shift(DOWN * (i - 1.5) * 1.2)

            func_group = VGroup(box, func_name, func_desc)
            func_boxes.add(func_group)

        # Animate function creation
        for func_group in func_boxes:
            self.play(Create(func_group))
            self.wait(0.5)

        # Highlight execute_order as key function
        execute_box = func_boxes[2][0]  # The rectangle
        self.play(execute_box.animate.scale(1.2).set_color(ORANGE))

        explanation = Text("execute_order is the core function that validates transactions\nbefore clients submit actual blockchain operations", font_size=18, color=WHITE)
        explanation.move_to(DOWN * 3)
        self.play(Write(explanation))

        self.wait(3)

        # Clear scene
        self.play(FadeOut(functions_title), FadeOut(func_boxes), FadeOut(explanation))

    def show_order_flow(self):
        # Order flow visualization
        flow_title = Text("Order Execution Flow", font_size=36, color=BLUE)
        self.play(Write(flow_title))

        # Create flow steps
        steps = [
            "1. Buyer calls execute_order",
            "2. Server validates order exists",
            "3. Check buyer SOL balance via RPC",
            "4. Check seller token balance via RPC",
            "5. If checks pass, update order book",
            "6. Client submits actual blockchain transaction"
        ]

        step_texts = VGroup()
        arrows = VGroup()

        for i, step in enumerate(steps):
            text = Text(step, font_size=18, color=WHITE)
            text.move_to(UP * (3 - i) + LEFT * 3)
            step_texts.add(text)

            if i > 0:
                arrow = Arrow(step_texts[i-1].get_right(), step_texts[i].get_left(), color=YELLOW)
                arrows.add(arrow)

        # Animate flow
        for i, text in enumerate(step_texts):
            self.play(Write(text))
            if i > 0:
                self.play(Create(arrows[i-1]))
            self.wait(0.8)

        # Add balance check details
        balance_check = Text("Balance Verification:\n• Buyer needs SOL for payment\n• Seller needs tokens for transfer", font_size=16, color=GREEN)
        balance_check.move_to(RIGHT * 3 + UP * 1)

        blockchain_note = Text("Note: Server only performs pre-checks.\nActual atomic swap must be handled by client.", font_size=14, color=RED)
        blockchain_note.move_to(RIGHT * 3 + DOWN * 1)

        self.play(Write(balance_check))
        self.wait(1)
        self.play(Write(blockchain_note))

        self.wait(3)

        # Clear scene
        self.play(FadeOut(flow_title), FadeOut(step_texts), FadeOut(arrows),
                 FadeOut(balance_check), FadeOut(blockchain_note))

    def show_summary(self):
        # Summary
        summary_title = Text("Summary", font_size=36, color=BLUE)
        self.play(Write(summary_title))

        summary_points = [
            "• MCP Server provides DEX functionality for ICO tokens",
            "• Orders are stored in JSON files with persistence",
            "• Four main tools: create, cancel, execute, get orders",
            "• execute_order performs pre-condition checks via Solana RPC",
            "• Server validates balances but doesn't execute blockchain transactions",
            "• Clients must handle actual atomic swaps after server validation"
        ]

        summary_text = VGroup()
        for i, point in enumerate(summary_points):
            text = Text(point, font_size=18, color=WHITE)
            text.move_to(DOWN * (i - 2) * 0.5)
            summary_text.add(text)

        # Animate summary
        for text in summary_text:
            self.play(Write(text))
            self.wait(0.5)

        # Final message
        final_message = Text("This DEX server enables secure token trading\nwith proper validation and persistence", font_size=20, color=YELLOW)
        final_message.move_to(DOWN * 3)
        self.play(Write(final_message))

        self.wait(4)

        # Clear scene
        self.play(FadeOut(summary_title), FadeOut(summary_text), FadeOut(final_message))

        # End scene
        thank_you = Text("Thank you for watching!", font_size=32, color=GREEN)
        self.play(Write(thank_you))
        self.wait(2)
        self.play(FadeOut(thank_you))

if __name__ == "__main__":
    # This allows running the animation directly
    pass