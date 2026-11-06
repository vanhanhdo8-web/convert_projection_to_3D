// ================================================
// BẢN VẼ KỸ THUẬT CƠ KHÍ - GÁ CHẠC LỖ TRÒN
// Đơn vị: mm
// ================================================

$fn = 100; // Độ mịn cho khối tròn

// Thông số kích thước
total_length = 65;
total_width  = 28;
total_height = 27;
base_height  = 12; // Chiều cao phần đế

step_length  = 32; // Chiều dài bậc trên (tính từ mép phải)

hole_x       = 20; // Tâm lỗ cách mép trái
hole_dia     = 13; // Đường kính lỗ tròn

slot_depth   = 14; // Chiều sâu rãnh chữ U (tính từ mép phải)
slot_width   = 18; // Chiều rộng rãnh chữ U

module ga_chac() {
    difference() {
        // Khối tổng thể (Gồm đế + Bậc trên)
        union() {
            // 1. Đế dưới
            cube([total_length, total_width, base_height]);
            
            // 2. Bậc phía trên (nằm ở phía phải)
            translate([total_length - step_length, 0, base_height])
                cube([step_length, total_width, total_height - base_height]);
        }
        
        // 3. Lỗ tròn xuyện qua đế bên trái
        translate([hole_x, total_width / 2, -1])
            cylinder(d = hole_dia, h = base_height + 2);
            
        // 4. Rãnh chữ U ở bậc trên bên phải
        translate([total_length - slot_depth, (total_width - slot_width) / 2, base_height - 0.1])
            cube([slot_depth + 1, slot_width, total_height - base_height + 1]);
    }
}

// Dựng hình
ga_chac();